import pytest
from src.app.reconcile import TOPIC_PROMPT, UNTAGGED, tag_topics

DOC = "transcripts/07_2024-11-12_ordering-logic-design"


def record(n: int, span: str = "Some words.") -> dict:
    """A statement as the extraction step writes it."""
    return {
        "id": f"{DOC}#{n}",
        "doc_id": DOC,
        "doc_type": "transcript",
        "stated_on": "2024-11-12",
        "position": f"{n} seconds",
        "lines": [n, n],
        "span": span,
        "act": "report",
        "actor": {"name": "Bo Ray", "label": None, "org": "RELEX", "role": None},
        "agreed_by": [],
    }


def tagging(*batches: list[tuple[str, str]]):
    """A model that answers each batch it is shown with the (label, topic) tags it is told to,
    and remembers what it was shown."""
    seen: list[str] = []
    answers = iter(batches)

    def chat(messages, schema=None):
        assert messages[0]["content"] == TOPIC_PROMPT
        seen.append(messages[1]["content"])
        return {"tags": [{"statement": s, "topic": t} for s, t in next(answers)]}

    chat.seen = seen
    return chat


def test_every_statement_gets_exactly_one_topic():
    records = [record(1), record(2), record(3)]
    chat = tagging([("S1", "ship-date"), ("S2", "ship-date"), ("S3", "field-removal")])
    topics, dropped = tag_topics(records, chat, 20, 40)
    assert topics == {
        f"{DOC}#1": "ship-date",
        f"{DOC}#2": "ship-date",
        f"{DOC}#3": "field-removal",
    }
    assert dict(dropped) == {}


def test_a_topic_already_in_use_is_shown_to_the_next_batch():
    chat = tagging([("S1", "ship-date")], [("S1", "ship-date")])
    tag_topics([record(1), record(2)], chat, 1, 40)
    assert "Topics already in use: none yet." in chat.seen[0]
    assert "Topics already in use: ship-date." in chat.seen[1]


def test_a_differently_spelled_topic_merges_onto_the_one_in_use():
    chat = tagging([("S1", "ship-date")], [("S1", "Ship  Date")], [("S1", "x-y")])
    topics, dropped = tag_topics([record(1), record(2), record(3)], chat, 1, 40)
    assert topics[f"{DOC}#2"] == "ship-date"
    assert "Topics already in use: ship-date." in chat.seen[2]
    assert dict(dropped) == {}


def test_a_tag_for_a_label_that_was_not_shown_is_dropped():
    chat = tagging([("S1", "ship-date"), ("S9", "field-removal")])
    topics, dropped = tag_topics([record(1)], chat, 20, 40)
    assert topics == {f"{DOC}#1": "ship-date"}
    assert dict(dropped) == {"label not shown in this batch": 1}


def test_a_topic_that_is_not_a_short_slug_is_dropped_and_its_statement_is_untagged():
    chat = tagging([("S1", "Shelf life: coverage!"), ("S2", "a" * 41), ("S3", "  ")])
    records = [record(1), record(2), record(3)]
    topics, dropped = tag_topics(records, chat, 20, 40)
    assert set(topics.values()) == {UNTAGGED}
    assert dict(dropped) == {"topic is not a short slug": 3, "statement not tagged": 3}


def test_a_statement_tagged_twice_keeps_the_first_tag():
    chat = tagging([("S1", "ship-date"), ("S1", "field-removal")])
    topics, dropped = tag_topics([record(1)], chat, 20, 40)
    assert topics == {f"{DOC}#1": "ship-date"}
    assert dict(dropped) == {"label tagged twice": 1}


def test_a_statement_the_model_forgot_lands_in_untagged():
    chat = tagging([("S1", "ship-date")])
    topics, dropped = tag_topics([record(1), record(2)], chat, 20, 40)
    assert topics == {f"{DOC}#1": "ship-date", f"{DOC}#2": UNTAGGED}
    assert dict(dropped) == {"statement not tagged": 1}


def test_the_reserved_untagged_cannot_come_from_the_model_and_is_never_offered_as_a_topic():
    chat = tagging([("S1", "Untagged")], [("S1", "ship-date")])
    topics, dropped = tag_topics([record(1), record(2)], chat, 1, 40)
    assert topics[f"{DOC}#1"] == UNTAGGED
    assert dict(dropped) == {"reserved topic": 1, "statement not tagged": 1}
    assert "untagged" not in chat.seen[1]


def test_the_vocabulary_shown_is_capped_and_ordered_by_use_then_name():
    chat = tagging(
        [("S1", "zeta"), ("S2", "zeta")],
        [("S1", "beta"), ("S2", "alpha")],
        [("S1", "gamma")],
    )
    tag_topics([record(n) for n in range(1, 6)], chat, 2, 2)
    assert "Topics already in use: zeta, alpha." in chat.seen[2]
    assert "beta" not in chat.seen[2].split("Statements:")[0]


def test_the_model_is_never_shown_a_real_statement_id_or_a_document_name():
    chat = tagging([("S1", "ship-date"), ("S2", "ship-date")], [("S1", "ship-date")])
    tag_topics([record(1), record(2), record(3)], chat, 2, 40)
    for shown in chat.seen:
        assert DOC not in shown
        assert "#" not in shown
    assert "[S1]" in chat.seen[0] and "[S2]" in chat.seen[0]
    assert "[S1]" in chat.seen[1] and "[S2]" not in chat.seen[1]  # labels restart each batch


def test_the_tagger_is_never_shown_a_statements_speech_act():
    """Asked to name a subject while looking at one, a small model copies the act and every
    topic comes back called "proposal". Stage A is shown no act at all. See D42."""
    chat = tagging([("S1", "ship-date")])
    tag_topics([record(1)], chat, 20, 40)
    assert "report" not in chat.seen[0]


@pytest.mark.parametrize("reserved", ["proposal", "agreement", "decision", "question", "untagged"])
def test_a_topic_named_after_a_speech_act_is_dropped(reserved: str):
    chat = tagging([("S1", reserved)])
    topics, dropped = tag_topics([record(1)], chat, 20, 40)
    assert topics[f"{DOC}#1"] == UNTAGGED
    assert dropped["reserved topic"] == 1

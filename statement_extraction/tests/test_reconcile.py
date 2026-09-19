import pytest
from src.app.reconcile import (
    RECONCILE_PROMPT,
    TOPIC_PROMPT,
    UNTAGGED,
    ReconcileError,
    _check,
    group,
    reconcile,
    reconcile_topic,
)

DOC = "transcripts/07_2024-11-12_ordering-logic-design"
SETTINGS = dict(
    batch=20,
    vocabulary_shown=40,
    topic_cap=40,
    max_untagged=0.1,
    max_topics=0.35,
    # Off by default in these tests: most of them hand reconcile() two or three statements on
    # one topic, which is exactly what the two gates are built to reject at corpus scale.
    max_topic_share=1.0,
    max_flagged=1.0,
    progress=lambda line: None,
)


def record(
    n: int,
    act: str = "report",
    *,
    stated_on: str = "2025-01-10",
    doc: str = DOC,
    message: int | None = None,
    agreed: bool = False,
    span: str | None = None,
) -> dict:
    """A statement as the extraction step writes it. A message number makes it an email."""
    return {
        "id": f"{doc}#{n}",
        "doc_id": doc,
        "doc_type": "email" if message else "transcript",
        "stated_on": stated_on,
        "position": f"message {message} of 4" if message else f"{n} seconds",
        "lines": [n, n],
        "span": span or f"Statement number {n}.",
        "act": act,
        "actor": {"name": "Ann Lee", "label": None, "org": "Acme Org", "role": None},
        "agreed_by": [{"name": "Bo Ray", "statement": "x#1"}] if agreed else [],
    }


def link(source: str, target: str, kind: str) -> dict:
    return {"from": source, "to": target, "kind": kind}


def reconciling(**parts):
    """A model that gives the same reconciliation every time, and remembers what it was shown."""
    seen: list[str] = []
    answer = {
        "relations": [],
        "statuses": [],
        "summary": {"text": "Shipping moved.", "statements": ["S1"]},
        "problems": [],
    } | parts

    def chat(messages, schema=None):
        assert messages[0]["content"] == RECONCILE_PROMPT
        seen.append(messages[1]["content"])
        return answer

    chat.seen = seen
    return chat


def run(statements: list[dict], **parts) -> tuple[dict, dict]:
    topic, dropped = reconcile_topic("ship-date", statements, reconciling(**parts))
    return topic, dict(dropped)


def pair(**late) -> list[dict]:
    """An earlier statement (S1, January) and a later one (S2, February)."""
    return [record(1), record(2, stated_on="2025-02-10", **late)]


def statuses(topic: dict) -> list[str]:
    return list(topic["statuses"].values())


def test_a_supersedes_link_makes_the_earlier_statement_stale():
    early, late = pair()
    topic, dropped = run([early, late], relations=[link("S2", "S1", "supersedes")])
    assert topic["statuses"] == {early["id"]: "stale", late["id"]: "current"}
    assert topic["relations"] == [{"from": late["id"], "to": early["id"], "kind": "supersedes"}]
    assert dropped == {}


def test_a_corrects_link_makes_the_corrected_statement_never_true():
    early, late = pair()
    topic, _ = run([early, late], relations=[link("S2", "S1", "corrects")])
    assert topic["statuses"] == {early["id"]: "never-true", late["id"]: "current"}


def test_never_true_wins_when_a_statement_is_both_corrected_and_superseded():
    first, second, third = record(1), record(2, stated_on="2025-02-10"), record(3)
    third["stated_on"] = "2025-03-10"
    relations = [link("S2", "S1", "supersedes"), link("S3", "S1", "corrects")]
    topic, _ = run([first, second, third], relations=relations)
    assert topic["statuses"][first["id"]] == "never-true"


def test_a_conflict_marks_both_statements_disputed_whichever_way_it_is_written():
    early, late = pair()
    for relation in (link("S1", "S2", "conflicts-with"), link("S2", "S1", "conflicts-with")):
        topic, _ = run([early, late], relations=[relation])
        assert statuses(topic) == ["disputed", "disputed"]


def test_the_same_conflict_written_both_ways_is_one_relation():
    early, late = pair()
    both = [link("S1", "S2", "conflicts-with"), link("S2", "S1", "conflicts-with")]
    topic, dropped = run([early, late], relations=both)
    assert len(topic["relations"]) == 1
    assert dropped == {"duplicate relation": 1}


def test_a_proposal_or_question_nothing_answers_is_unresolved():
    topic, _ = run([record(1, "proposal"), record(2, "question")])
    assert statuses(topic) == ["unresolved", "unresolved"]


def test_a_proposal_that_is_answered_is_not_unresolved():
    early, late = pair()
    early["act"] = "proposal"
    topic, _ = run([early, late], relations=[link("S2", "S1", "answers")])
    assert statuses(topic) == ["current", "current"]


def test_a_proposal_someone_already_accepted_is_not_unresolved():
    topic, _ = run([record(1, "proposal", agreed=True)])
    assert statuses(topic) == ["current"]


def test_a_statement_no_relation_touches_stays_current():
    topic, _ = run([record(1, "decision"), record(2, "report"), record(3, "objection")])
    assert statuses(topic) == ["current", "current", "current"]


def test_a_relation_naming_a_statement_outside_the_topic_is_dropped():
    topic, dropped = run(pair(), relations=[link("S2", "S9", "supersedes")])
    assert topic["relations"] == []
    assert dropped == {"relation names a statement outside the topic": 1}


def test_a_relation_to_itself_is_dropped():
    topic, dropped = run(pair(), relations=[link("S1", "S1", "supersedes")])
    assert topic["relations"] == []
    assert dropped == {"relation to itself": 1}


def test_a_relation_of_a_kind_we_do_not_have_is_dropped():
    topic, dropped = run(pair(), relations=[link("S2", "S1", "retracts")])
    assert topic["relations"] == []
    assert dropped == {"relation of an unknown kind": 1}


def test_a_relation_written_twice_is_kept_once():
    twice = [link("S2", "S1", "supersedes")] * 2
    topic, dropped = run(pair(), relations=twice)
    assert len(topic["relations"]) == 1
    assert dropped == {"duplicate relation": 1}


def test_a_supersession_that_runs_backwards_in_time_is_dropped_and_makes_nothing_stale():
    early, late = pair()
    topic, dropped = run([early, late], relations=[link("S1", "S2", "supersedes")])
    assert topic["relations"] == []
    assert statuses(topic) == ["current", "current"]
    assert dropped == {"supersedes runs backwards in time": 1}


def test_a_correction_written_on_the_same_day_is_kept():
    first, second = record(1), record(2)
    topic, dropped = run([first, second], relations=[link("S2", "S1", "corrects")])
    assert topic["statuses"][first["id"]] == "never-true"
    assert dropped == {}


def test_a_supersession_written_on_the_same_day_is_kept():
    first, second = record(1), record(2)
    topic, _ = run([first, second], relations=[link("S2", "S1", "supersedes")])
    assert topic["statuses"][first["id"]] == "stale"


def test_a_correction_may_run_backwards_in_time_because_only_supersedes_is_date_guarded():
    # The planted case: a March hypercare statement says a September report was never right.
    early, late = pair()
    topic, dropped = run([early, late], relations=[link("S1", "S2", "corrects")])
    assert topic["statuses"][late["id"]] == "never-true"
    assert dropped == {}


def test_a_status_no_relation_justifies_falls_back_to_current():
    early, late = pair()
    claimed = [{"statement": "S1", "status": "stale"}, {"statement": "S2", "status": "never-true"}]
    topic, dropped = run([early, late], statuses=claimed)
    assert statuses(topic) == ["current", "current"]
    assert dropped == {"status differs from what the relations give": 2}


def test_a_status_the_model_leaves_off_is_still_derived_from_the_relations():
    early, late = pair()
    topic, dropped = run([early, late], relations=[link("S2", "S1", "corrects")], statuses=[])
    assert topic["statuses"][early["id"]] == "never-true"
    assert dropped == {}


def test_a_status_for_an_unknown_statement_or_of_an_unknown_kind_is_dropped():
    claimed = [{"statement": "S9", "status": "stale"}, {"statement": "S1", "status": "retired"}]
    topic, dropped = run(pair(), statuses=claimed)
    assert statuses(topic) == ["current", "current"]
    assert dropped == {"status for an unknown statement or of an unknown kind": 2}


def test_a_summary_keeps_the_receipts_that_resolve_and_drops_the_rest():
    early, late = pair()
    summary = {"text": "Shipping moved to February.", "statements": ["S2", "S9", "S2", "S1"]}
    topic, dropped = run([early, late], summary=summary)
    assert topic["summary"] == {
        "text": "Shipping moved to February.",
        "statements": [late["id"], early["id"]],
    }
    assert dropped == {"summary receipt not in the topic": 1}


def test_a_summary_left_with_no_receipts_is_dropped_whole():
    topic, dropped = run(pair(), summary={"text": "Shipping moved.", "statements": ["S9"]})
    assert topic["summary"] is None
    assert dropped == {
        "summary receipt not in the topic": 1,
        "summary without text or receipts": 1,
    }


def test_a_summary_with_no_text_is_dropped_whole():
    topic, dropped = run(pair(), summary={"text": "  ", "statements": ["S1"]})
    assert topic["summary"] is None
    assert dropped == {"summary without text or receipts": 1}


@pytest.mark.parametrize("quoted", ['He said "ship on Friday".', "He said “ship on Friday”."])
def test_a_summary_that_quotes_the_record_is_dropped(quoted: str):
    topic, dropped = run(pair(), summary={"text": quoted, "statements": ["S1"]})
    assert topic["summary"] is None
    assert dropped == {"summary contains a quotation": 1}


def test_an_apostrophe_is_not_a_quotation():
    summary = {"text": "The customer's field was removed.", "statements": ["S1"]}
    topic, dropped = run(pair(), summary=summary)
    assert topic["summary"]["text"] == "The customer's field was removed."
    assert dropped == {}


def test_a_problem_a_relation_supports_is_kept():
    early, late = pair()
    problem = {"kind": "never-true", "statements": ["S2", "S1"], "note": "S1 was never right."}
    topic, dropped = run(
        [early, late], relations=[link("S2", "S1", "corrects")], problems=[problem]
    )
    assert topic["problems"] == [
        {
            "kind": "never-true",
            "topic": "ship-date",
            "statements": [late["id"], early["id"]],
            "note": "S1 was never right.",
        }
    ]
    assert dropped == {}


def test_a_problem_no_surviving_relation_supports_is_dropped():
    problem = {"kind": "reversal", "statements": ["S1", "S2"], "note": "It was reversed."}
    _, dropped = run(pair(), problems=[problem])
    assert dropped == {"problem no relation supports": 1}


def test_a_problem_supported_only_by_a_relation_between_other_statements_is_dropped():
    first, second, third = record(1), record(2, stated_on="2025-02-10"), record(3)
    third["stated_on"] = "2025-03-10"
    problem = {"kind": "reversal", "statements": ["S1", "S3"], "note": "It was reversed."}
    _, dropped = run(
        [first, second, third], relations=[link("S2", "S1", "supersedes")], problems=[problem]
    )
    assert dropped == {"problem no relation supports": 1}


def test_a_problem_naming_a_statement_outside_the_topic_is_dropped():
    problem = {"kind": "unanswered", "statements": ["S1", "S9"], "note": "Nobody answered."}
    _, dropped = run([record(1, "question")], problems=[problem])
    assert dropped == {"problem names a statement outside the topic": 1}


def test_a_problem_naming_nothing_is_dropped():
    problem = {"kind": "unanswered", "statements": [], "note": "Nobody answered."}
    _, dropped = run([record(1, "question")], problems=[problem])
    assert dropped == {"problem names no statement": 1}


@pytest.mark.parametrize("note", ["", "x" * 301, 'It says "no".'])
def test_a_problem_note_that_is_empty_long_or_quoted_is_dropped(note: str):
    problem = {"kind": "unanswered", "statements": ["S1"], "note": note}
    topic, dropped = run([record(1, "question")], problems=[problem])
    assert dropped == {"problem note empty, too long or quoted": 1}
    assert [p["note"] for p in topic["problems"]] == [
        f"{record(1)['id']} was proposed or asked, and nothing in the record answers it."
    ]


def test_a_problem_of_an_unknown_kind_is_dropped():
    problem = {"kind": "mistake", "statements": ["S1"], "note": "Something is off."}
    _, dropped = run([record(1, "question")], problems=[problem])
    assert dropped == {"problem of an unknown kind": 1}


def test_every_flagged_statement_ends_up_named_in_a_problem_from_a_template_if_need_be():
    a, b, c, d, e = (record(n, stated_on=f"2025-0{n}-10") for n in range(1, 6))
    e["act"] = "question"
    relations = [
        link("S3", "S1", "supersedes"),
        link("S4", "S2", "corrects"),
        link("S4", "S3", "conflicts-with"),
    ]
    topic, _ = run([a, b, c, d, e], relations=relations)
    assert statuses(topic) == ["stale", "never-true", "disputed", "disputed", "unresolved"]
    assert topic["problems"] == [
        {
            "kind": "reversal",
            "topic": "ship-date",
            "statements": [a["id"], c["id"]],
            "note": f"{c['id']} supersedes {a['id']}; the record still reads as if {a['id']} "
            "stands.",
        },
        {
            "kind": "never-true",
            "topic": "ship-date",
            "statements": [b["id"], d["id"]],
            "note": f"{d['id']} says {b['id']} was wrong when it was recorded.",
        },
        {
            "kind": "conflict",
            "topic": "ship-date",
            "statements": [d["id"], c["id"]],
            "note": f"{d['id']} and {c['id']} cannot both be true, and nothing in the record "
            "settles which holds.",
        },
        {
            "kind": "unanswered",
            "topic": "ship-date",
            "statements": [e["id"]],
            "note": f"{e['id']} was proposed or asked, and nothing in the record answers it.",
        },
    ]


def test_a_flagged_statement_the_model_already_named_gets_no_template_problem():
    early, late = pair()
    problem = {"kind": "reversal", "statements": ["S1", "S2"], "note": "Shipping was moved."}
    topic, _ = run([early, late], relations=[link("S2", "S1", "supersedes")], problems=[problem])
    assert [p["note"] for p in topic["problems"]] == ["Shipping was moved."]


def test_the_model_is_shown_labels_never_a_real_statement_id():
    chat = reconciling()
    reconcile_topic("ship-date", pair(), chat)
    assert "[S1]" in chat.seen[0] and "[S2]" in chat.seen[0]
    assert DOC not in chat.seen[0]
    assert "#" not in chat.seen[0]


def test_the_prompt_forbids_deciding_a_status_from_dates():
    assert "Never decide a status from dates" in RECONCILE_PROMPT


def test_statements_are_shown_oldest_first_across_documents():
    later = record(1, stated_on="2025-03-10", doc="emails/03_x")
    earlier = record(1, stated_on="2025-01-10", doc="transcripts/01_y")
    middle = record(1, stated_on="2025-02-10", doc="reports/02_z")
    topics = {r["id"]: "ship-date" for r in (later, earlier, middle)}
    [(name, ordered)] = group([later, earlier, middle], topics, 40)
    assert name == "ship-date"
    assert [r["id"] for r in ordered] == [earlier["id"], middle["id"], later["id"]]


def test_a_thread_is_shown_in_the_order_it_was_written_not_the_order_it_is_filed():
    # A thread lists its newest message first: message 4 is the oldest, and is filed last.
    newest = record(5, message=3, doc="emails/07_x")
    oldest = record(9, message=4, doc="emails/07_x")
    topics = {r["id"]: "ship-date" for r in (newest, oldest)}
    [(_, ordered)] = group([newest, oldest], topics, 40)
    assert [r["id"] for r in ordered] == [oldest["id"], newest["id"]]


def test_topics_are_reconciled_largest_first_and_untagged_is_not_one_of_them():
    records = [record(n) for n in range(1, 6)]
    topics = dict(zip((r["id"] for r in records), ["b", "a", "a", UNTAGGED, "a"], strict=True))
    groups = group(records, topics, 40)
    assert [(name, len(statements)) for name, statements in groups] == [("a", 3), ("b", 1)]


def test_an_oversized_topic_is_cut_into_consecutive_chunks_of_near_equal_size():
    records = [record(n, stated_on=f"2025-01-{n:02d}") for n in range(1, 8)]
    topics = {r["id"]: "ship-date" for r in records}
    groups = group(records, topics, 3)
    assert [name for name, _ in groups] == [
        "ship-date (1 of 3)",
        "ship-date (2 of 3)",
        "ship-date (3 of 3)",
    ]
    assert [len(statements) for _, statements in groups] == [3, 2, 2]
    assert [r["id"] for _, statements in groups for r in statements] == [r["id"] for r in records]


def dispatching(tags: list[str | None], **parts):
    """A model for the whole pass: it tags the first batch as told (None leaves a statement
    out) and reconciles every topic the same way."""
    reconcile_answer = reconciling(**parts)

    def chat(messages, schema=None):
        if messages[0]["content"] == TOPIC_PROMPT:
            return {
                "tags": [
                    {"statement": f"S{n}", "topic": topic}
                    for n, topic in enumerate(tags, 1)
                    if topic
                ]
            }
        return reconcile_answer(messages, schema)

    chat.reconciled = reconcile_answer.seen
    return chat


def test_a_whole_pass_reconciles_each_topic_and_carries_untagged_statements_along_as_current():
    records = [record(n, stated_on=f"2025-01-{n:02d}") for n in range(1, 11)]
    records[4]["act"] = "proposal"
    chat = dispatching(["a", "a", "a", "a", None, "b", "b", "b", "b", "b"])
    lines: list[str] = []
    topics, problems, dropped = reconcile(records, chat, **SETTINGS | {"progress": lines.append})
    assert [t["topic"] for t in topics] == ["b", "a", UNTAGGED]
    assert len(chat.reconciled) == 2  # nothing is asked about the untagged statement
    untagged = topics[-1]
    assert untagged["summary"] is None and untagged["relations"] == []
    assert list(untagged["statuses"].values()) == ["current"]  # a proposal, but never examined
    assert problems == []
    assert dict(dropped) == {"statement not tagged": 1}
    assert lines[0].startswith("Tagged 10 statements: 2 topics, 1 untagged")
    assert lines[1].startswith("b: 5 statements, 0 relations")


def test_a_whole_pass_collects_the_problems_of_every_topic():
    records = [record(1, "question"), record(2, "question")]
    chat = dispatching(["a", "b"])
    _, problems, _ = reconcile(records, chat, **SETTINGS | {"max_topics": 1.0})
    assert [(p["topic"], p["kind"]) for p in problems] == [("a", "unanswered"), ("b", "unanswered")]


def test_too_many_untagged_statements_stop_the_pass():
    records = [record(n) for n in range(1, 11)]
    chat = dispatching(["a"] + [None] * 9)
    with pytest.raises(ReconcileError, match="untagged"):
        reconcile(records, chat, **SETTINGS)
    assert chat.reconciled == []


def test_exactly_the_allowed_share_of_untagged_statements_passes():
    records = [record(n) for n in range(1, 11)]
    chat = dispatching(["a"] * 4 + ["b"] * 5 + [None])
    topics, _, _ = reconcile(records, chat, **SETTINGS)
    assert [t["topic"] for t in topics] == ["b", "a", UNTAGGED]


def test_a_topic_for_every_statement_stops_the_pass():
    records = [record(n) for n in range(1, 5)]
    chat = dispatching(["a", "b", "c", "d"])
    with pytest.raises(ReconcileError, match="fragmented"):
        reconcile(records, chat, **SETTINGS)
    assert chat.reconciled == []


def test_one_topic_holding_most_of_the_record_stops_the_pass():
    """The opposite of fragmentation, and the failure neither earlier gate can see: a run whose
    every statement lands in one bucket. See D44."""
    records = [record(n) for n in range(1, 11)]
    chat = dispatching(["a"] * 9 + ["b"])
    with pytest.raises(ReconcileError, match="collapsed"):
        reconcile(records, chat, **SETTINGS | {"max_topic_share": 0.5})
    assert chat.reconciled == []


def test_exactly_the_allowed_topic_share_passes():
    records = [record(n) for n in range(1, 11)]
    chat = dispatching(["a"] * 5 + ["b"] * 5)
    topics, _, _ = reconcile(records, chat, **SETTINGS | {"max_topic_share": 0.5})
    assert sorted(t["topic"] for t in topics) == ["a", "b"]


def test_a_relation_chain_that_flags_the_whole_topic_stops_the_pass():
    """A model that links each statement to the next one in the list marks nearly everything
    never-true, and `corrects` is not date-guarded, so nothing else rejects it. See D44."""
    records = [record(n, stated_on=f"2025-01-{n:02d}") for n in range(1, 5)]
    chain = [link(f"S{n + 1}", f"S{n}", "corrects") for n in range(1, 4)]
    chat = dispatching(["a"] * 4, relations=chain)
    with pytest.raises(ReconcileError, match="a chain the model walked"):
        reconcile(records, chat, **SETTINGS | {"max_topics": 1.0, "max_flagged": 0.5})


def test_a_topic_flagged_within_the_allowance_passes():
    records = [record(n, stated_on=f"2025-01-{n:02d}") for n in range(1, 5)]
    chat = dispatching(["a"] * 4, relations=[link("S2", "S1", "corrects")])
    topics, _, _ = reconcile(records, chat, **SETTINGS | {"max_topics": 1.0, "max_flagged": 0.5})
    assert sorted(topics[0]["statuses"].values()) == ["current", "current", "current", "never-true"]


def test_unresolved_statements_do_not_count_towards_the_flagged_gate():
    """`unresolved` is a property of one statement, not a link between two, so a topic of
    unanswered proposals is not a chain and must not be refused as one."""
    records = [record(n, "proposal") for n in range(1, 5)]
    chat = dispatching(["a"] * 4)
    topics, _, _ = reconcile(records, chat, **SETTINGS | {"max_topics": 1.0, "max_flagged": 0.5})
    assert set(topics[0]["statuses"].values()) == {"unresolved"}


def held(*statements: dict) -> dict:
    """A topic as reconcile_topic returns it, less the problems."""
    return {
        "topic": "ship-date",
        "summary": None,
        "relations": [],
        "statuses": {s["id"]: "current" for s in statements},
        "statements": list(statements),
    }


def test_the_whole_artifact_gate_passes_what_it_should():
    early, late = pair()
    _check([held(early, late)], [], [early, late])


def test_the_gate_stops_a_statement_that_went_missing_or_turned_up_twice():
    early, late = pair()
    with pytest.raises(ReconcileError, match="exactly one topic"):
        _check([held(early)], [], [early, late])
    with pytest.raises(ReconcileError, match="exactly one topic"):
        _check([held(early, late), held(late) | {"topic": "other"}], [], [early, late])


def test_the_gate_stops_a_relation_that_leaves_its_topic():
    early, late = pair()
    topic = held(early) | {"relations": [link(late["id"], early["id"], "supersedes")]}
    with pytest.raises(ReconcileError, match="relation"):
        _check([topic, held(late) | {"topic": "other"}], [], [early, late])


def test_the_gate_stops_a_summary_that_cites_a_statement_from_elsewhere():
    early, late = pair()
    cited = {"text": "Shipping moved.", "statements": [late["id"]]}
    with pytest.raises(ReconcileError, match="summary"):
        _check(
            [held(early) | {"summary": cited}, held(late) | {"topic": "other"}], [], [early, late]
        )


def test_the_gate_stops_a_problem_that_names_a_statement_from_elsewhere():
    early, late = pair()
    problem = {"kind": "conflict", "topic": "ship-date", "statements": [late["id"]], "note": "x"}
    with pytest.raises(ReconcileError, match="problem"):
        _check([held(early), held(late) | {"topic": "other"}], [problem], [early, late])


def test_the_gate_stops_a_status_outside_the_five():
    early, late = pair()
    topic = held(early, late)
    topic["statuses"][early["id"]] = "retired"
    with pytest.raises(ReconcileError, match="status"):
        _check([topic], [], [early, late])


def test_the_gate_stops_a_flagged_statement_no_problem_names():
    early, late = pair()
    topic = held(early, late)
    topic["statuses"][early["id"]] = "stale"
    with pytest.raises(ReconcileError, match="named in no problem"):
        _check([topic], [], [early, late])


def test_a_summary_that_states_a_figure_the_topic_does_not_is_dropped():
    """The highest-value invention in a derived artifact is a number: the archive is full of
    half-said percentages, and a summary that completes one has invented a source. See D44."""
    topic, dropped = run(
        pair(), summary={"text": "Remediation is at 60 percent.", "statements": ["S1"]}
    )
    assert topic["summary"] is None
    assert dropped == {"summary states a figure the topic does not": 1}


def test_a_summary_may_repeat_a_figure_the_topic_does_contain():
    statements = [record(1, span="Coverage is 82 percent."), record(2)]
    topic, dropped = run(
        statements, summary={"text": "Coverage stands at 82.", "statements": ["S1"]}
    )
    assert topic["summary"] == {"text": "Coverage stands at 82.", "statements": [f"{DOC}#1"]}
    assert dropped == {}


def test_a_problem_note_that_states_a_figure_the_topic_does_not_is_dropped():
    topic, dropped = run(
        pair(),
        relations=[link("S2", "S1", "corrects")],
        problems=[
            {"kind": "never-true", "statements": ["S1", "S2"], "note": "It was 40 all along."}
        ],
    )
    assert [p["note"] for p in topic["problems"]] == [
        f"{DOC}#2 says {DOC}#1 was wrong when it was recorded."
    ]
    assert dropped["problem note states a figure the topic does not"] == 1

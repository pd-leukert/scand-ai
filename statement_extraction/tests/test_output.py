import json

from src.app import output
from src.app.output import NOT_STATED, to_reconciled, to_statement


def record(**overrides) -> dict:
    base = {
        "id": "emails/07#4",
        "doc_id": "emails/07",
        "doc_type": "email",
        "doc_date": "2025-11-24",
        "stated_on": "2025-11-18",
        "position": "message 4 of 4",
        "lines": [93, 94],
        "span": "It must be excluded at source before the next extract runs.",
        "claim": "The speaker wants the field excluded at source.",
        "act": "proposal",
        "handling": "none",
        "actor": {"name": "Priya Nair", "label": None, "org": "Acme Org", "role": "IT Lead"},
        "agreed_by": [],
    }
    return base | overrides


def test_a_record_becomes_the_shape_the_backend_loads():
    assert to_statement(record()) == {
        "id": "emails/07#4",
        "document_id": "emails/07",
        "doc_type": "email",
        "location": {
            "page": None,
            "line_start": 93,
            "line_end": 94,
            "position": "message 4 of 4",
        },
        "verbatim_span": "It must be excluded at source before the next extract runs.",
        "claim": "The speaker wants the field excluded at source.",
        "speech_act": "proposal",
        "handling": "none",
        "actor": {
            "name": "Priya Nair",
            "label": None,
            "organization": "Acme Org",
            "role": "IT Lead",
        },
        "agreed_by": [],
        "statement_date": "2025-11-18",
        "document_date": "2025-11-24",
    }


def test_a_speaker_the_file_does_not_name_is_shown_by_the_files_label():
    unnamed = {"name": None, "label": "Guest 1", "org": None, "role": None}
    actor = to_statement(record(actor=unnamed))["actor"]
    assert actor == {
        "name": "Guest 1",
        "label": "Guest 1",
        "organization": NOT_STATED,
        "role": NOT_STATED,
    }


def test_what_no_document_states_is_not_stated_never_guessed():
    actor = {"name": "Kwame Boateng", "label": None, "org": None, "role": None}
    shown = to_statement(record(actor=actor))["actor"]
    assert (shown["organization"], shown["role"]) == (NOT_STATED, NOT_STATED)
    assert shown["label"] is None


def test_an_agreement_keeps_who_agreed_and_where():
    agreed = {
        "name": "Nadia Haddad",
        "label": None,
        "org": "RELEX",
        "role": None,
        "statement": "emails/07#9",
    }
    [entry] = to_statement(record(agreed_by=[agreed]))["agreed_by"]
    assert entry == {
        "name": "Nadia Haddad",
        "label": None,
        "organization": "RELEX",
        "role": NOT_STATED,
        "statement": "emails/07#9",
    }


def held(name: str, *records: dict, **overrides) -> dict:
    """A topic as the reconciliation pass returns it."""
    topic = {
        "topic": name,
        "summary": None,
        "relations": [],
        "statuses": {r["id"]: "current" for r in records},
        "statements": list(records),
    }
    return topic | overrides


def test_the_reconciled_file_nests_every_statement_exactly_once():
    first, second, third = (record(id=f"emails/07#{n}") for n in (1, 2, 3))
    topics = [held("ship-date", first, second), held("field-removal", third)]
    reconciled = to_reconciled(topics, [], "2026-09-19")
    nested = [s["id"] for topic in reconciled["topics"] for s in topic["statements"]]
    assert nested == ["emails/07#1", "emails/07#2", "emails/07#3"]
    assert [t["topic"] for t in reconciled["topics"]] == ["ship-date", "field-removal"]


def test_a_reconciled_statement_is_a_statement_plus_its_status():
    stale = record()
    topic = held("ship-date", stale, statuses={stale["id"]: "stale"})
    [nested] = to_reconciled([topic], [], "2026-09-19")["topics"][0]["statements"]
    assert nested == to_statement(stale) | {"status": "stale"}


def test_a_relation_lives_on_its_topic_once_and_not_on_each_statement():
    early, late = record(id="emails/07#1"), record(id="emails/07#2")
    relation = {"from": late["id"], "to": early["id"], "kind": "supersedes"}
    topic = held("ship-date", early, late, relations=[relation])
    [written] = to_reconciled([topic], [], "2026-09-19")["topics"]
    assert written["relations"] == [relation]
    assert all("relations" not in s for s in written["statements"])


def test_a_topic_with_no_surviving_summary_still_carries_its_statements():
    only = record()
    [topic] = to_reconciled([held("ship-date", only)], [], "2026-09-19")["topics"]
    assert topic["summary"] is None
    assert [s["id"] for s in topic["statements"]] == [only["id"]]


def test_the_counts_are_what_is_actually_in_the_file():
    early, late, other = (record(id=f"emails/07#{n}") for n in (1, 2, 3))
    relation = {"from": late["id"], "to": early["id"], "kind": "supersedes"}
    problem = {"kind": "reversal", "topic": "a", "statements": [early["id"]], "note": "n"}
    topics = [held("a", early, late, relations=[relation]), held("b", other)]
    reconciled = to_reconciled(topics, [problem, problem], "2026-09-19")
    assert reconciled["generated_on"] == "2026-09-19"
    assert (
        reconciled["statement_count"],
        reconciled["topic_count"],
        reconciled["relation_count"],
        reconciled["problem_count"],
    ) == (3, 2, 1, 2)
    assert reconciled["problem_count"] == len(reconciled["problems"])


def test_without_prose_the_file_carries_ids_and_enums_only(monkeypatch):
    only = record()
    summary = {"text": "Shipping moved to February.", "statements": [only["id"]]}
    problem = {"kind": "unanswered", "topic": "a", "statements": [only["id"]], "note": "Nobody."}
    monkeypatch.setattr(output, "KEEP_PROSE", False)
    reconciled = to_reconciled([held("a", only, summary=summary)], [problem], "2026-09-19")
    assert reconciled["topics"][0]["summary"] is None
    assert reconciled["problems"] == [{**problem, "note": ""}]
    assert "February" not in json.dumps(reconciled) and "Nobody" not in json.dumps(reconciled)

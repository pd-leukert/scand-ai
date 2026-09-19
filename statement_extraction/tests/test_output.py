import json

import pytest
from src.app import output
from src.app.output import NOT_STATED, to_reconciled, to_statement

DOC = "emails/07"

# What the reconciled file carries once per document instead of on each statement (D44).
DOCUMENTS = [
    {"id": DOC, "type": "email", "date": "2025-11-18", "people": ["Priya Nair"], "summary": "OP_ID"}
]


def record(**overrides) -> dict:
    base = {
        "id": f"{DOC}#1",
        "doc_id": DOC,
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
        "claim": "The speaker wants the field excluded at source.",
        "speech_act": "proposal",
        "actor": {
            "name": "Priya Nair",
            "organization": "Acme Org",
        },
        "statement_date": "2025-11-18",
    }


def test_a_speaker_the_file_does_not_name_is_shown_by_the_files_label():
    unnamed = {"name": None, "label": "Guest 1", "org": None, "role": None}
    actor = to_statement(record(actor=unnamed))["actor"]
    assert actor == {
        "name": "Guest 1",
        "organization": NOT_STATED,
    }


def test_what_no_document_states_is_not_stated_never_guessed():
    actor = {"name": "Kwame Boateng", "label": None, "org": None, "role": None}
    shown = to_statement(record(actor=actor))["actor"]
    assert shown["organization"] == NOT_STATED


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


def reconciled_from(topics: list[dict], problems: list[dict] | None = None) -> dict:
    return to_reconciled(topics, problems or [], "2026-09-19", DOCUMENTS)


def test_the_reconciled_file_nests_every_statement_exactly_once():
    first, second, third = (record(id=f"{DOC}#{n}") for n in (1, 2, 3))
    topics = [held("ship-date", first, second), held("field-removal", third)]
    reconciled = reconciled_from(topics)
    nested = [s["id"] for topic in reconciled["topics"] for s in topic["statements"]]
    assert nested == [f"{DOC}#1", f"{DOC}#2", f"{DOC}#3"]
    assert [t["topic"] for t in reconciled["topics"]] == ["ship-date", "field-removal"]


def test_a_reconciled_statement_is_its_id_a_statement_and_its_status():
    stale = record()
    topic = held("ship-date", stale, statuses={stale["id"]: "stale"})
    [nested] = reconciled_from([topic])["topics"][0]["statements"]
    assert nested == {"id": stale["id"]} | to_statement(stale) | {"status": "stale"}


def test_a_reconciled_statement_carries_nothing_the_statements_file_dropped():
    """The reduction D37 made to the statements file, made to this one (D44): whatever a
    statement says about its document, its place in it or who agreed to it is not written."""
    [nested] = reconciled_from([held("ship-date", record())])["topics"][0]["statements"]
    assert set(nested) == {"id", "claim", "speech_act", "actor", "statement_date", "status"}
    assert set(nested["actor"]) == {"name", "organization"}


def test_what_is_true_of_a_whole_document_is_written_once_in_a_table():
    first, second = record(id=f"{DOC}#1"), record(id=f"{DOC}#2")
    reconciled = reconciled_from([held("a", first), held("b", second)])
    assert reconciled["documents"] == DOCUMENTS
    assert "document_id" not in json.dumps(reconciled["topics"])
    assert "document_date" not in json.dumps(reconciled["topics"])


def test_a_statement_from_a_document_the_file_does_not_list_is_refused():
    """The backend takes the date from that table, so a statement without an entry is a
    citation with no date. It has to fail where it is written, not where it is read."""
    stray = record(id="emails/99#1", doc_id="emails/99")
    with pytest.raises(ValueError, match="emails/99"):
        reconciled_from([held("ship-date", stray)])


def test_a_relation_lives_on_its_topic_once_and_not_on_each_statement():
    early, late = record(id=f"{DOC}#1"), record(id=f"{DOC}#2")
    relation = {"from": late["id"], "to": early["id"], "kind": "supersedes"}
    topic = held("ship-date", early, late, relations=[relation])
    [written] = reconciled_from([topic])["topics"]
    assert written["relations"] == [relation]
    assert all("relations" not in s for s in written["statements"])


def test_a_topic_with_no_surviving_summary_still_carries_its_statements():
    only = record()
    [topic] = reconciled_from([held("ship-date", only)])["topics"]
    assert topic["summary"] is None
    assert [s["id"] for s in topic["statements"]] == [only["id"]]


def test_the_counts_are_what_is_actually_in_the_file():
    early, late, other = (record(id=f"{DOC}#{n}") for n in (1, 2, 3))
    relation = {"from": late["id"], "to": early["id"], "kind": "supersedes"}
    problem = {"kind": "reversal", "topic": "a", "statements": [early["id"]], "note": "n"}
    topics = [held("a", early, late, relations=[relation]), held("b", other)]
    reconciled = reconciled_from(topics, [problem, problem])
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
    reconciled = reconciled_from([held("a", only, summary=summary)], [problem])
    assert reconciled["topics"][0]["summary"] is None
    assert reconciled["problems"] == [{**problem, "note": ""}]
    assert "February" not in json.dumps(reconciled) and "Nobody" not in json.dumps(reconciled)

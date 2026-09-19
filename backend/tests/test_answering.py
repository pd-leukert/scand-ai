import json
from pathlib import Path

import pytest
from src.app import config
from src.app.llm_client import (
    CITATION_DELIMITER,
    _aliased,
    _aliases,
    _build_messages,
    _resolve_citations,
    _split_response,
    context_shortfall,
)
from src.app.statements import load_record, load_statements, load_statements_record

DOC = "emails/07_op-id"
OTHER = "transcripts/17_go-no-go"
NOTE = f"{DOC}#12 supersedes {DOC}#1; the record still reads as if {DOC}#1 stands."


def statement(n: int, doc: str = DOC, *, act: str = "report", status: str = "current") -> dict:
    return {
        "id": f"{doc}#{n}",
        "claim": f"Claim number {n}.",
        "actor": {"name": "Priya Nair", "organization": "Acme"},
        "speech_act": act,
        "statement_date": "2025-11-24",
        "status": status,
    }


def reconciled(tmp_path: Path, **parts) -> str:
    """A reconciled file in the shape extraction writes (D44): two documents, and a topic in
    which statement 12 supersedes statement 1 — ids where one is the start of the other."""
    body = {
        "documents": [
            {"id": DOC, "type": "email", "date": "2025-11-24", "people": [], "summary": "OP_ID"},
            {"id": OTHER, "type": "transcript", "date": "2025-11-17", "people": [], "summary": ""},
        ],
        "topics": [
            {
                "topic": "op-id-field",
                "summary": {"text": "The field was dropped.", "statements": [f"{DOC}#12"]},
                "relations": [{"from": f"{DOC}#12", "to": f"{DOC}#1", "kind": "supersedes"}],
                "statements": [
                    statement(1, status="stale"),
                    statement(12),
                    statement(3, OTHER),
                ],
            }
        ],
        "problems": [
            {
                "kind": "reversal",
                "topic": "op-id-field",
                "statements": [f"{DOC}#1", f"{DOC}#12"],
                "note": NOTE,
            }
        ],
    } | parts
    path = tmp_path / "reconciled.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return str(path)


@pytest.fixture
def record(tmp_path: Path):
    load_record.cache_clear()
    return load_record(reconciled(tmp_path))


def test_the_loader_restores_the_document_of_each_statement_from_its_id_and_the_table(record):
    twelve = record.statements[f"{DOC}#12"]
    assert twelve.document_id == DOC
    assert str(twelve.document_date) == "2025-11-24"
    other = record.statements[f"{OTHER}#3"]
    assert (other.document_id, str(other.document_date)) == (OTHER, "2025-11-17")


def test_a_statement_whose_document_the_file_does_not_list_fails_to_load(tmp_path: Path):
    load_record.cache_clear()
    stray = {"topic": "t", "relations": [], "statements": [statement(1, "emails/99")]}
    with pytest.raises(ValueError, match="emails/99"):
        load_record(reconciled(tmp_path, topics=[stray], problems=[]))


def test_a_receipt_names_the_statement_that_justifies_a_status(record):
    assert record.receipts == {f"{DOC}#1": [f"{DOC}#12"]}


def test_every_statement_gets_its_own_short_alias_in_the_records_order(record):
    aliases = _aliases(record)
    assert list(aliases.values()) == ["s1", "s2", "s3"]
    assert list(aliases) == [f"{DOC}#1", f"{DOC}#12", f"{OTHER}#3"]


def test_the_model_is_shown_aliases_and_never_a_real_id(record):
    sent = _build_messages("What happened to OP_ID?", record)[1]["content"]
    assert "#" not in sent, "a real id (or a path with one) reached the model"
    assert DOC not in sent and OTHER not in sent


def test_a_reconciled_statement_is_shown_with_only_what_the_file_carries(record):
    payload = json.loads(_build_messages("q", record)[1]["content"].split("\n")[1])
    [topic] = payload["topics"]
    [first, *_] = topic["statements"]
    assert set(first) == {"id", "claim", "actor", "speech_act", "statement_date", "status"}
    assert first["statement_date"] == "2025-11-24"  # a day, not a datetime
    assert topic["relations"] == [{"from": "s2", "to": "s1", "kind": "supersedes"}]
    assert topic["summary"]["statements"] == ["s2"]
    assert payload["problems"][0]["statements"] == ["s1", "s2"]


def test_a_note_naming_an_id_that_starts_another_is_aliased_longest_first():
    """`emails/07_op-id#1` is the start of `emails/07_op-id#12`. Replace the short one first and
    the long one is left as `s1` + `2` — a wrong alias that looks like a real one."""
    aliases = {f"{DOC}#1": "s1", f"{DOC}#12": "s2"}
    want = "s2 supersedes s1; the record still reads as if s1 stands."
    assert _aliased(NOTE, aliases, [f"{DOC}#1", f"{DOC}#12"]) == want
    assert _aliased(NOTE, aliases, [f"{DOC}#12", f"{DOC}#1"]) == want


def test_an_id_that_is_the_tail_of_another_is_replaced_after_it():
    """The other way round: `a/x#1` sits inside `b/a/x#1`, so replacing it first leaves the
    longer id as `b` + `s1`. The lookahead cannot see this one; the ordering has to."""
    aliases = {"a/x#1": "s1", "b/a/x#1": "s2"}
    note = "b/a/x#1 supersedes a/x#1."
    assert _aliased(note, aliases, ["a/x#1", "b/a/x#1"]) == "s2 supersedes s1."


def test_an_id_the_note_names_but_the_problem_does_not_list_is_left_alone_not_half_replaced():
    """The other protection: a note that mentions `#12` while only `#1` is listed must not have
    its `#1` swapped for an alias and leave `s1` + `2` behind. Templated notes only name what
    their problem lists, so this is a guard on the boundary, not something seen in a run."""
    aliases = {f"{DOC}#1": "s1", f"{DOC}#12": "s2"}
    assert _aliased(f"See {DOC}#12 and {DOC}#1.", aliases, [f"{DOC}#1"]) == f"See {DOC}#12 and s1."


def test_a_problem_note_reaches_the_model_with_aliases_in_it(record):
    payload = json.loads(_build_messages("q", record)[1]["content"].split("\n")[1])
    assert payload["problems"][0]["note"] == (
        "s2 supersedes s1; the record still reads as if s1 stands."
    )


def test_a_cited_alias_becomes_a_citation_copied_from_our_own_record(record):
    [citation] = _resolve_citations(["s1"], record)
    assert citation.statement_id == f"{DOC}#1"
    assert (citation.document_id, citation.claim) == (DOC, "Claim number 1.")
    assert citation.status == "stale"
    assert citation.status_receipts == [f"{DOC}#12"]


def test_anything_the_model_cites_that_we_did_not_hand_out_is_dropped(record):
    """The trust boundary, unchanged by the aliasing (D21): an invented alias, a real id
    the model was never shown, and an empty string all resolve to nothing."""
    cited = ["s99", f"{DOC}#1", "", "s2"]
    citations = _resolve_citations(cited, record)
    assert [(c.marker, c.statement_id) for c in citations] == [(4, f"{DOC}#12")]


def test_a_reply_is_split_into_prose_and_the_aliases_it_cites():
    raw = f"It was dropped [1].\n{CITATION_DELIMITER}\n" + '["s2", "s1"]'
    assert _split_response(raw) == ("It was dropped [1].\n", ["s2", "s1"])
    assert _split_response("No citations here.") == ("No citations here.", [])


def test_a_statements_only_record_is_grouped_by_document_and_carries_no_status(tmp_path: Path):
    body = {
        "documents": [
            {
                "id": DOC,
                "type": "email",
                "date": "2025-11-24",
                "people": [],
                "summary": "",
                "statements": [
                    {k: v for k, v in statement(n).items() if k not in ("id", "status")}
                    for n in (1, 2)
                ],
            }
        ]
    }
    path = tmp_path / "statements.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    load_statements.cache_clear()
    record = load_statements_record(str(path))
    assert record.reconciled is False
    payload = json.loads(_build_messages("q", record)[1]["content"].split("\n")[1])
    [group] = payload
    assert (group["document_id"], group["document_date"]) == (DOC, "2025-11-24")
    assert [s["id"] for s in group["statements"]] == ["s1", "s2"]
    assert "status" not in json.dumps(payload)
    assert _resolve_citations(["s1"], record)[0].status is None


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """A backend configured against a small reconciled file and a given context."""
    monkeypatch.setenv("LLM_BASE_URL", "http://ollama.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "any-model")
    monkeypatch.setenv("RECONCILED_FILE_PATH", reconciled(tmp_path))
    load_record.cache_clear()

    def configure(num_ctx: str | None):
        if num_ctx is None:
            monkeypatch.delenv("LLM_NUM_CTX", raising=False)
        else:
            monkeypatch.setenv("LLM_NUM_CTX", num_ctx)
        config.get_settings.cache_clear()

    yield configure
    config.get_settings.cache_clear()


def test_a_record_that_does_not_fit_the_served_context_is_reported_not_answered(served):
    served("100")
    tokens, num_ctx = context_shortfall("What happened to OP_ID?")
    assert num_ctx == 100 and tokens > 100


def test_a_record_that_fits_is_not_reported(served):
    served("1000000")
    assert context_shortfall("What happened to OP_ID?") is None


def test_leaving_the_context_unset_turns_the_guard_off(served):
    served(None)
    assert context_shortfall("What happened to OP_ID?") is None

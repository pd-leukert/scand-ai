import json
from pathlib import Path

import httpx
import pytest
from src.app import extract
from src.app.reconcile import RECONCILE_PROMPT, TOPIC_PROMPT

TRANSCRIPT = """*** SYNTHETIC DATA.
Meeting: Kickoff
Customer: Acme Org
Date: 2024-03-20
Phase: Pre-Sales
Attendees: Bo Ray (RELEX)

Bo Ray
0:040:04
BR
Bo Ray 4 seconds
We will ship on Friday.
"""

STATEMENT = {
    "unit": 1,
    "span": "We will ship on Friday.",
    "claim": "Bo Ray said the work ships on Friday.",
    "act": "report",
    "org": None,
    "role": None,
    "handling": "none",
}


RECONCILIATION = {
    "relations": [],
    "statuses": [],
    "summary": {"text": "Bo Ray said the work ships on Friday.", "statements": ["S1"]},
    "problems": [],
}


@pytest.fixture
def job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A one-document corpus, a model that finds one statement, and the job's settings."""
    folder = tmp_path / "corpus" / "transcripts"
    folder.mkdir(parents=True)
    (folder / "01_kickoff.txt").write_text(TRANSCRIPT, encoding="utf-8")
    monkeypatch.setenv("EXTRACTION_LLM_MODEL", "any-model")
    monkeypatch.setenv("CORPUS_DIR", str(tmp_path / "corpus"))
    monkeypatch.setenv("STATEMENTS_FILE_PATH", str(tmp_path / "statements.json"))
    monkeypatch.setenv("RECONCILED_FILE_PATH", str(tmp_path / "reconciled.json"))
    # One statement is one topic, which the fragmentation gate would rightly refuse — and that
    # one topic then holds the whole run, which the collapse gate would refuse for the same
    # reason. Both are corpus-scale gates; a one-document job trips them legitimately.
    monkeypatch.setenv("RECONCILE_MAX_TOPICS", "1")
    monkeypatch.setenv("RECONCILE_MAX_TOPIC_SHARE", "1")
    monkeypatch.setenv("RECONCILE_MAX_FLAGGED", "1")
    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: answering())
    return tmp_path / "statements.json"


def answering(statement: dict = STATEMENT, tags: list[dict] | None = None):
    """A model for both passes: it finds the one statement, tags it, and reconciles the topic.
    The tags it gives can be replaced, to make the second pass fail."""
    if tags is None:
        tags = [{"statement": "S1", "topic": "ship-date"}]

    def chat(messages: list[dict[str, str]], schema: dict | None = None) -> dict:
        system = messages[0]["content"]
        if system == TOPIC_PROMPT:
            return {"tags": tags}
        if system == RECONCILE_PROMPT:
            return RECONCILIATION
        return {"statements": [statement]}

    return chat


def reconciled_file(job: Path) -> Path:
    return job.with_name("reconciled.json")


def test_a_run_that_finds_statements_writes_the_file_and_succeeds(job: Path):
    assert extract.main([]) == 0
    written = json.loads(job.read_text(encoding="utf-8"))
    assert list(written) == ["statements"]
    assert [s["document_id"] for s in written["statements"]] == ["transcripts/01_kickoff"]


def test_a_run_that_reconciles_writes_both_files_and_succeeds(job: Path):
    assert extract.main([]) == 0
    reconciled = json.loads(reconciled_file(job).read_text(encoding="utf-8"))
    assert reconciled["statement_count"] == 1
    [topic] = reconciled["topics"]
    assert topic["topic"] == "ship-date"
    assert topic["summary"]["statements"] == ["transcripts/01_kickoff#1"]
    assert [(s["id"], s["status"]) for s in topic["statements"]] == [
        ("transcripts/01_kickoff#1", "current")
    ]


def test_a_failed_reconciliation_fails_the_job_and_writes_no_reconciled_file(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: answering(tags=[]))
    assert extract.main([]) == 1
    assert job.exists()  # the first pass finished, so its file is a complete record
    assert not reconciled_file(job).exists()
    assert not reconciled_file(job).with_name("reconciled.json.tmp").exists()


def test_a_model_that_cannot_be_reached_during_reconciliation_fails_the_job(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    def down(messages: list[dict[str, str]], schema: dict | None = None) -> dict:
        if messages[0]["content"] == TOPIC_PROMPT:
            raise httpx.ConnectError("down")
        return answering()(messages, schema)

    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: down)
    assert extract.main([]) == 1
    assert not reconciled_file(job).exists()


def test_a_failed_reconciliation_leaves_an_earlier_reconciled_file_alone(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    reconciled_file(job).write_text("earlier record\n", encoding="utf-8")
    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: answering(tags=[]))
    assert extract.main([]) == 1
    assert reconciled_file(job).read_text(encoding="utf-8") == "earlier record\n"


def test_a_document_with_no_statements_fails_before_anything_is_reconciled(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    other = job.parent / "corpus" / "transcripts" / "02_other.txt"
    other.write_text(TRANSCRIPT, encoding="utf-8")
    asked: list[str] = []

    def only_the_first(messages: list[dict[str, str]], schema: dict | None = None) -> dict:
        asked.append(messages[0]["content"])
        if "01_kickoff" in messages[1]["content"]:
            return answering()(messages, schema)
        return {"statements": []}

    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: only_the_first)
    assert extract.main([]) == 1
    assert TOPIC_PROMPT not in asked
    assert not reconciled_file(job).exists()


def test_reconciliation_falls_back_to_the_extraction_model_when_none_is_named(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    models: list[str] = []

    def choose(client: httpx.Client, model: str, num_ctx: int):
        models.append(model)
        return answering()

    monkeypatch.setattr(extract, "_ollama_chat", choose)
    assert extract.main([]) == 0
    assert models == ["any-model", "any-model"]


def test_a_named_reconciliation_model_is_used_for_reconciliation_only(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    models: list[str] = []

    def choose(client: httpx.Client, model: str, num_ctx: int):
        models.append(model)
        return answering()

    monkeypatch.setattr(extract, "_ollama_chat", choose)
    monkeypatch.setenv("RECONCILE_LLM_MODEL", "other-model")
    assert extract.main([]) == 0
    assert models == ["any-model", "other-model"]


def test_the_run_reports_what_the_reconciled_file_costs_in_context(
    job: Path, capsys: pytest.CaptureFixture[str]
):
    assert extract.main([]) == 0
    printed = capsys.readouterr().out
    assert "statements.json" in printed and "reconciled.json" in printed
    # The line is what whoever sets OLLAMA_CONTEXT_LENGTH reads, so it names the variables
    # rather than leaving the number to be acted on by someone who knows what it means (D43).
    assert "tokens in the answering context" in printed
    assert "OLLAMA_CONTEXT_LENGTH and LLM_NUM_CTX above" in printed


def test_the_run_prints_the_problems_it_found(
    job: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(
        extract, "_ollama_chat", lambda *_: answering(STATEMENT | {"act": "question"})
    )
    assert extract.main([]) == 0
    printed = capsys.readouterr().out
    assert "[unanswered] ship-date: transcripts/01_kickoff#1" in printed
    assert json.loads(reconciled_file(job).read_text(encoding="utf-8"))["problem_count"] == 1


def test_a_run_that_finds_nothing_fails_and_leaves_the_old_file_alone(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    job.write_text("earlier record\n", encoding="utf-8")
    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: lambda messages: {"statements": []})
    assert extract.main([]) == 1
    assert job.read_text(encoding="utf-8") == "earlier record\n"
    assert not reconciled_file(job).exists()


def test_a_document_with_no_statements_fails_the_job_but_keeps_the_rest(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    other = job.parent / "corpus" / "transcripts" / "02_other.txt"
    other.write_text(TRANSCRIPT, encoding="utf-8")

    def only_the_first(messages: list[dict[str, str]]) -> dict:
        return (
            {"statements": [STATEMENT]}
            if "01_kickoff" in messages[1]["content"]
            else {"statements": []}
        )

    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: only_the_first)
    assert extract.main([]) == 1
    assert len(json.loads(job.read_text(encoding="utf-8"))["statements"]) == 1


def test_no_model_named_means_no_run(job: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("EXTRACTION_LLM_MODEL")
    assert extract.main([]) == 2
    assert not job.exists()

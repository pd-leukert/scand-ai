import json
from pathlib import Path

import pytest
from src.app import extract

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


@pytest.fixture
def job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A one-document corpus, a model that finds one statement, and the job's settings."""
    folder = tmp_path / "corpus" / "transcripts"
    folder.mkdir(parents=True)
    (folder / "01_kickoff.txt").write_text(TRANSCRIPT, encoding="utf-8")
    monkeypatch.setenv("EXTRACTION_LLM_MODEL", "any-model")
    monkeypatch.setenv("CORPUS_DIR", str(tmp_path / "corpus"))
    monkeypatch.setenv("STATEMENTS_FILE_PATH", str(tmp_path / "statements.json"))
    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: lambda messages: answer(messages))
    return tmp_path / "statements.json"


def answer(messages: list[dict[str, str]]) -> dict:
    return {"statements": [STATEMENT]}


def test_a_run_that_finds_statements_writes_the_file_and_succeeds(job: Path):
    assert extract.main([]) == 0
    written = json.loads(job.read_text(encoding="utf-8"))
    assert list(written) == ["statements"]
    assert [s["document_id"] for s in written["statements"]] == ["transcripts/01_kickoff"]


def test_a_documents_file_lands_before_the_next_document_is_asked_for(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    """Progress has to be visible while a slow model is still working, not only once the
    whole run is done — so 01_kickoff's file must exist by the time 02_other is asked for."""
    other = job.parent / "corpus" / "transcripts" / "02_other.txt"
    other.write_text(TRANSCRIPT, encoding="utf-8")
    first_doc_file = job.parent / "documents" / "transcripts" / "01_kickoff.json"

    def check_order(messages: list[dict[str, str]]) -> dict:
        if "02_other" in messages[1]["content"]:
            assert first_doc_file.exists()
            written = json.loads(first_doc_file.read_text(encoding="utf-8"))
            assert [s["document_id"] for s in written["statements"]] == ["transcripts/01_kickoff"]
        return answer(messages)

    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: check_order)
    assert extract.main([]) == 0


def test_a_successful_run_cleans_up_the_per_document_files(job: Path):
    assert extract.main([]) == 0
    assert not (job.parent / "documents").exists()


def test_a_run_that_finds_nothing_leaves_the_per_document_file_for_inspection(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    """The merged file is never written in this all-empty case (see the next test), so the
    per-document files are the only record of what actually ran — not cleaned up here."""
    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: lambda messages: {"statements": []})
    assert extract.main([]) == 1
    doc_file = job.parent / "documents" / "transcripts" / "01_kickoff.json"
    assert json.loads(doc_file.read_text(encoding="utf-8")) == {"statements": []}


def test_a_run_that_finds_nothing_fails_and_leaves_the_old_file_alone(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    job.write_text("earlier record\n", encoding="utf-8")
    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: lambda messages: {"statements": []})
    assert extract.main([]) == 1
    assert job.read_text(encoding="utf-8") == "earlier record\n"


def test_a_document_with_no_statements_fails_the_job_but_keeps_the_rest(
    job: Path, monkeypatch: pytest.MonkeyPatch
):
    other = job.parent / "corpus" / "transcripts" / "02_other.txt"
    other.write_text(TRANSCRIPT, encoding="utf-8")

    def only_the_first(messages: list[dict[str, str]]) -> dict:
        return answer(messages) if "01_kickoff" in messages[1]["content"] else {"statements": []}

    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: only_the_first)
    assert extract.main([]) == 1
    assert len(json.loads(job.read_text(encoding="utf-8"))["statements"]) == 1


def test_no_model_named_means_no_run(job: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("EXTRACTION_LLM_MODEL")
    assert extract.main([]) == 2
    assert not job.exists()

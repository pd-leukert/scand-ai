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
    monkeypatch.setenv("EXTRACTION_MODEL", "any-model")
    monkeypatch.setenv("CORPUS_DIR", str(tmp_path / "corpus"))
    monkeypatch.setenv("STATEMENTS_PATH", str(tmp_path / "statements.jsonl"))
    monkeypatch.setattr(extract, "_ollama_chat", lambda *_: lambda messages: answer(messages))
    return tmp_path / "statements.jsonl"


def answer(messages: list[dict[str, str]]) -> dict:
    return {"statements": [STATEMENT]}


def test_a_run_that_finds_statements_writes_the_file_and_succeeds(job: Path):
    assert extract.main([]) == 0
    lines = job.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert '"doc_id": "transcripts/01_kickoff"' in lines[0]


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
    assert len(job.read_text(encoding="utf-8").splitlines()) == 1


def test_no_model_named_means_no_run(job: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("EXTRACTION_MODEL")
    assert extract.main([]) == 2
    assert not job.exists()

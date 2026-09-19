import json
from pathlib import Path

from src.app.statements import load_statements


def statement(n: int, name: str) -> dict:
    return {
        "claim": "We will ship on Friday.",
        "actor": {"name": name, "organization": "RELEX"},
        "speech_act": "report",
        "statement_date": f"2025-11-24T09:{n:02d}:00",
    }


def write(path: Path, *names: str) -> str:
    """The grouped shape the file is stored in (D36): one document, its statements nested."""
    document = {
        "id": "transcripts/01_kickoff",
        "type": "transcript",
        "date": "2025-11-24",
        "people": list(names),
        "summary": "A kickoff call.",
        "statements": [statement(n, name) for n, name in enumerate(names, start=1)],
    }
    path.write_text(json.dumps({"documents": [document]}, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_a_file_rewritten_between_two_requests_is_read_afresh(tmp_path: Path):
    path = write(tmp_path / "statements.json", "Kwame Boateng")
    assert load_statements(path)["transcripts/01_kickoff#1"].actor.name == "Kwame Boateng"

    write(tmp_path / "statements.json", "[former RELEX employee]")

    expected = "[former RELEX employee]"
    assert load_statements(path)["transcripts/01_kickoff#1"].actor.name == expected


def test_names_outside_ascii_load_whatever_the_platform_default_encoding_is(tmp_path: Path):
    path = write(tmp_path / "statements.json", "Henrik Sørensen", "Nadia Öberg")

    loaded = load_statements(path)

    assert [s.actor.name for s in loaded.values()] == ["Henrik Sørensen", "Nadia Öberg"]

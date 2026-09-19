import json
from pathlib import Path

from src.app.statements import load_statements


def statement(n: int, name: str) -> dict:
    return {
        "id": f"transcripts/01#{n}",
        "document_id": "transcripts/01_kickoff",
        "location": {"page": None, "line_start": n, "line_end": n, "position": f"{n} minutes"},
        "verbatim_span": "We will ship on Friday.",
        "actor": {"name": name, "organization": "RELEX", "role": "Consultant"},
        "agreed_by": [],
        "speech_act": "report",
        "statement_date": "2025-11-24",
        "document_date": "2025-11-24",
    }


def write(path: Path, *names: str) -> str:
    statements = [statement(n, name) for n, name in enumerate(names, start=1)]
    path.write_text(json.dumps({"statements": statements}, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_a_file_rewritten_between_two_requests_is_read_afresh(tmp_path: Path):
    path = write(tmp_path / "statements.json", "Kwame Boateng")
    assert load_statements(path)["transcripts/01#1"].actor.name == "Kwame Boateng"

    write(tmp_path / "statements.json", "[former RELEX employee]")

    assert load_statements(path)["transcripts/01#1"].actor.name == "[former RELEX employee]"


def test_names_outside_ascii_load_whatever_the_platform_default_encoding_is(tmp_path: Path):
    path = write(tmp_path / "statements.json", "Henrik Sørensen", "Nadia Öberg")

    loaded = load_statements(path)

    assert [s.actor.name for s in loaded.values()] == ["Henrik Sørensen", "Nadia Öberg"]

import json
from pathlib import Path

import pytest
from src.app import delete
from tests.test_deletion import archive, stmts, text_of


@pytest.fixture
def statements_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "statements.json"
    path.write_text(
        json.dumps({"documents": archive()}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("STATEMENTS_FILE_PATH", str(path))
    return path


def written(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["documents"]


def test_the_file_is_rewritten_without_the_person_and_the_receipt_is_printed(
    statements_file: Path, capsys: pytest.CaptureFixture[str]
):
    assert delete.main(["Kwame Boateng"]) == 0

    after = written(statements_file)
    assert "Kwame" not in text_of(after) and "Boateng" not in text_of(after)
    assert [d["id"] for d in after] == [d["id"] for d in archive()]
    assert len(stmts(after)) == len(stmts(archive()))
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["deleted"]["name"] == "Kwame Boateng"
    assert not list(statements_file.parent.glob("*.tmp"))


def test_other_people_and_non_ascii_names_survive_the_rewrite(statements_file: Path):
    delete.main(["Kwame Boateng"])

    # Nadia Öberg is only mentioned, never a speaker, and must come out exactly as she went in.
    assert "Nadia Öberg" in statements_file.read_text(encoding="utf-8")
    assert "Priya Nair" in text_of(written(statements_file))


def test_a_dry_run_prints_the_receipt_and_changes_nothing(
    statements_file: Path, capsys: pytest.CaptureFixture[str]
):
    before = statements_file.read_bytes()

    assert delete.main(["Kwame Boateng", "--dry-run"]) == 0

    assert statements_file.read_bytes() == before
    assert json.loads(capsys.readouterr().out)["deleted"]["name"] == "Kwame Boateng"


def test_a_name_nobody_has_fails_and_leaves_the_file_alone(
    statements_file: Path, capsys: pytest.CaptureFixture[str]
):
    before = statements_file.read_bytes()

    assert delete.main(["Ada Lovelace"]) == 1

    assert statements_file.read_bytes() == before
    assert "nothing was changed" in capsys.readouterr().err


def test_deleting_the_same_person_twice_leaves_the_second_run_with_nothing_to_do(
    statements_file: Path,
):
    assert delete.main(["Kwame Boateng"]) == 0
    once = statements_file.read_bytes()

    assert delete.main(["Kwame Boateng"]) == 1

    assert statements_file.read_bytes() == once


def test_a_missing_statements_file_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setenv("STATEMENTS_FILE_PATH", str(tmp_path / "nothing.json"))

    assert delete.main(["Kwame Boateng"]) == 2

    assert "No statements file" in capsys.readouterr().err


def test_per_document_files_an_interrupted_run_left_behind_are_reported(
    statements_file: Path, capsys: pytest.CaptureFixture[str]
):
    (statements_file.parent / "documents").mkdir()

    assert delete.main(["Kwame Boateng"]) == 0

    assert "still holds the name" in capsys.readouterr().err

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from src.app.main import app
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


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def written(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["documents"]


def test_a_deletion_rewrites_the_file_and_returns_the_receipt(
    client: TestClient, statements_file: Path
):
    response = client.post("/delete", json={"name": "Kwame Boateng"})

    assert response.status_code == 200
    receipt = response.json()
    assert receipt["deleted"]["name"] == "Kwame Boateng"
    assert receipt["deleted"]["placeholder"] == "[former RELEX employee]"
    after = written(statements_file)
    assert "Kwame" not in text_of(after) and "Boateng" not in text_of(after)
    assert len(stmts(after)) == len(stmts(archive()))


def test_the_receipt_says_who_was_left_when_a_first_name_could_mean_two_people(
    client: TestClient, statements_file: Path
):
    receipt = client.post("/delete", json={"name": "Nadia"}).json()

    assert receipt["deleted"]["name"] == "Nadia Haddad"
    assert [p["name"] for p in receipt["considered"] if p["outcome"] == "left"] == ["Nadia Öberg"]
    assert any("Nadia Öberg" in note for note in receipt["left_in_place"])
    assert "Nadia Öberg" in statements_file.read_text(encoding="utf-8")


def test_a_name_nobody_has_leaves_the_file_alone(client: TestClient, statements_file: Path):
    before = statements_file.read_bytes()

    response = client.post("/delete", json={"name": "Ada Lovelace"})

    assert response.status_code == 200
    assert response.json()["deleted"] is None
    assert statements_file.read_bytes() == before


def test_an_empty_name_is_rejected_without_touching_the_file(
    client: TestClient, statements_file: Path
):
    before = statements_file.read_bytes()

    assert client.post("/delete", json={"name": ""}).status_code == 422

    assert statements_file.read_bytes() == before


def test_a_missing_statements_file_is_not_a_silent_success(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("STATEMENTS_FILE_PATH", str(tmp_path / "nothing.json"))

    response = client.post("/delete", json={"name": "Kwame Boateng"})

    assert response.status_code == 503
    assert "no statements file" in response.json()["detail"].lower()

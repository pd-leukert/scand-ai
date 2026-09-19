import copy
import json

from src.app.deletion import PLACEHOLDERS, delete_person


def person(name, org="RELEX"):
    return {"name": name, "organization": org}


def statement(actor, claim, n=1):
    return {
        "claim": claim,
        "actor": actor,
        "speech_act": "report",
        "statement_date": f"2025-11-24T09:{n:02d}:00",
    }


def document(statements, doc_id="transcripts/01_kickoff", people=(), summary="A kickoff call."):
    """One document block exactly as the statements file stores it (D36): what is true of
    every statement in it carried once, the statements nested under it."""
    return {
        "id": doc_id,
        "type": "transcript",
        "date": "2025-11-24",
        "people": list(people),
        "summary": summary,
        "statements": list(statements),
    }


def archive():
    kwame, nadia = person("Kwame Boateng"), person("Nadia Haddad")
    priya = person("Priya Nair", org="Acme Org")
    return [
        document(
            [
                statement(kwame, "Kwame Boateng can purge the landing zone.", 1),
                statement(
                    priya,
                    "Priya Nair sends the request to Kwame, "
                    "or writes to k.boateng@relexsolutions.example.",
                    2,
                ),
                statement(nadia, "Nadia here. Nadia Haddad agrees.", 3),
                statement(priya, "Not Nadia Öberg, the other one. Nadia Haddad, employee four.", 4),
                statement(priya, "Thanks, Boateng, that helps.", 5),
                statement(nadia, "Nadia Haddad accepted, and so did Priya Nair.", 6),
            ],
            people=["Kwame Boateng", "Priya Nair", "Nadia Haddad"],
            summary="Kickoff call run by Kwame Boateng.",
        )
    ]


def stmts(documents):
    """Every statement in the file, flat, so a test can index the one it means."""
    return [s for document in documents for s in document["statements"]]


def text_of(documents):
    return json.dumps(documents, ensure_ascii=False)


def test_a_full_name_is_replaced_in_every_field_the_name_sits_in():
    result, receipt = delete_person(archive(), "Kwame Boateng")
    placeholder = PLACEHOLDERS["relex"]
    after = stmts(result)
    assert after[0]["actor"]["name"] == placeholder
    assert after[0]["claim"] == f"{placeholder} can purge the landing zone."
    assert "Boateng" not in text_of(result) and "Kwame" not in text_of(result)
    assert receipt["deleted"]["placeholder"] == placeholder


def test_the_claim_is_redacted_too_including_emails_and_bare_names():
    result, _ = delete_person(archive(), "Kwame Boateng")
    placeholder = PLACEHOLDERS["relex"]
    after = stmts(result)
    assert after[1]["claim"] == (
        f"Priya Nair sends the request to {placeholder}, or writes to {placeholder}."
    )
    assert after[4]["claim"] == f"Thanks, {placeholder}, that helps."


def test_the_document_header_is_swept_as_well_as_the_statements():
    """people and summary live on the document, not the statement — a name survives in a
    header just as well as in a claim (D45)."""
    result, _ = delete_person(archive(), "Kwame Boateng")
    placeholder = PLACEHOLDERS["relex"]
    assert result[0]["people"] == [placeholder, "Priya Nair", "Nadia Haddad"]
    assert result[0]["summary"] == f"Kickoff call run by {placeholder}."


def test_the_neighbouring_statements_survive_with_their_content():
    before = archive()
    result, receipt = delete_person(before, "Kwame Boateng")
    after, original = stmts(result), stmts(before)
    assert len(after) == len(original)
    assert after[2] == original[2]
    # Counted over statements: 1, 2 and 5 name him. The document header changing is not a
    # statement changing.
    assert receipt["deleted"]["statements_changed"] == 3
    assert after[0]["speech_act"] == "report"


def test_the_document_envelope_keeps_its_shape():
    result, _ = delete_person(archive(), "Kwame Boateng")
    assert [d["id"] for d in result] == ["transcripts/01_kickoff"]
    assert result[0]["type"] == "transcript" and result[0]["date"] == "2025-11-24"
    assert len(result[0]["statements"]) == 6


def test_the_input_is_left_as_it_was():
    before = archive()
    snapshot = copy.deepcopy(before)
    delete_person(before, "Kwame Boateng")
    assert before == snapshot


def test_a_person_from_the_customer_gets_the_customer_placeholder():
    result, receipt = delete_person(archive(), "Priya Nair")
    assert receipt["deleted"]["placeholder"] == PLACEHOLDERS["customer"]
    assert "Priya" not in text_of(result) and "Nair" not in text_of(result)


def test_a_partner_gets_the_partner_placeholder():
    partner = person("Ruth Oyelaran", org="Meridian Consulting")
    archive_ = [document([statement(partner, "Ruth Oyelaran can help.")])]
    _, receipt = delete_person(archive_, "Ruth Oyelaran")
    assert receipt["deleted"]["placeholder"] == PLACEHOLDERS["partner"]


def test_two_spellings_of_one_person_are_one_person():
    henrik = [
        document(
            [
                statement(person("Henrik Sørensen"), "Henrik Sørensen says it is his account."),
                statement(
                    person("Priya Nair", "Acme Org"),
                    "Henrik Sorensen said henrik.sorensen@relexsolutions.example.",
                ),
                statement(person("Priya Nair", "Acme Org"), "Sørensen, Henrik will call."),
            ]
        )
    ]
    for spelling in ("Henrik Sørensen", "Henrik Sorensen", "henrik sorensen"):
        result, receipt = delete_person(henrik, spelling)
        assert "orensen" not in text_of(result) and "ørensen" not in text_of(result)
        assert receipt["deleted"]["spellings"] == ["Henrik Sorensen", "Henrik Sørensen"]


def test_delete_nadia_removes_the_best_evidenced_nadia_and_says_who_was_left():
    result, receipt = delete_person(archive(), "Nadia")
    assert receipt["deleted"]["name"] == "Nadia Haddad"
    outcomes = {c["name"]: c["outcome"] for c in receipt["considered"]}
    assert outcomes == {"Nadia Haddad": "removed", "Nadia Öberg": "left"}
    assert "Nadia Öberg" in stmts(result)[3]["claim"]
    assert "Haddad" not in text_of(result)


def test_a_first_name_shared_with_someone_else_is_left_alone_and_the_receipt_says_so():
    result, receipt = delete_person(archive(), "Nadia Haddad")
    assert stmts(result)[2]["claim"].startswith("Nadia here.")
    assert any("Nadia" in item and "Nadia Öberg" in item for item in receipt["left_in_place"])


def test_the_exact_full_name_beats_a_first_name_pick():
    result, receipt = delete_person(archive(), "Nadia Öberg")
    assert receipt["deleted"]["name"] == "Nadia Öberg"
    assert receipt["deleted"]["placeholder"] == PLACEHOLDERS["unknown"]
    assert stmts(result)[3]["claim"].startswith("Not [former participant]")
    assert stmts(result)[2] == stmts(archive())[2]


def test_a_name_nobody_has_changes_nothing_and_says_so():
    before = archive()
    result, receipt = delete_person(before, "Zoe Nobody")
    assert result == before
    assert receipt["deleted"] is None


def test_a_speaker_the_file_does_not_name_is_never_a_person():
    """The file no longer carries a separate label field — output._actor folds it into
    actor.name (D37) — so "Guest 1" arrives looking like any other name (D45)."""
    for label in ("Guest 1", "Unknown Speaker", "Them"):
        unnamed = {"name": label, "organization": "Not stated"}
        before = [document([statement(unnamed, "Hello.")]), *archive()]
        result, receipt = delete_person(before, label)
        assert result == before and receipt["deleted"] is None


def test_an_unnamed_speaker_is_not_offered_as_a_person_to_delete():
    unnamed = {"name": "Guest 1", "organization": "Not stated"}
    before = [document([statement(unnamed, "Hello.")]), *archive()]
    _, receipt = delete_person(before, "Kwame Boateng")
    assert "Guest 1" not in {c["name"] for c in receipt["considered"]}


def test_ids_and_dates_are_never_swept():
    odd = document(
        [statement(person("Kwame Boateng"), "Hello.")], doc_id="transcripts/kwame-boateng-notes"
    )
    result, _ = delete_person([odd], "Kwame Boateng")
    assert result[0]["id"] == "transcripts/kwame-boateng-notes"
    assert result[0]["date"] == "2025-11-24"
    assert result[0]["statements"][0]["statement_date"] == "2025-11-24T09:01:00"


def test_a_second_deletion_of_the_same_person_finds_nobody():
    once, _ = delete_person(archive(), "Kwame Boateng")
    twice, receipt = delete_person(once, "Kwame Boateng")
    assert twice == once and receipt["deleted"] is None


def test_phone_numbers_are_reported_as_not_covered():
    talker = document(
        [statement(person("Kwame Boateng"), "Kwame Boateng says call +351 913 882 145.")],
        people=["Kwame Boateng"],
    )
    _, receipt = delete_person([talker], "Kwame Boateng")
    assert any("phone" in item for item in receipt["left_in_place"])

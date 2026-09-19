import copy
import json

from src.app.deletion import PLACEHOLDERS, delete_person


def person(name, org="RELEX", role="Consultant", label=None):
    return {"name": name, "label": label, "organization": org, "role": role}


def statement(n, actor, span, claim="A claim.", agreed_by=()):
    return {
        "id": f"transcripts/01#{n}",
        "document_id": "transcripts/01_kickoff",
        "doc_type": "transcript",
        "location": {"page": None, "line_start": n, "line_end": n},
        "position": f"{n} minutes",
        "verbatim_span": span,
        "claim": claim,
        "speech_act": "report",
        "handling": "none",
        "actor": actor,
        "agreed_by": list(agreed_by),
        "statement_date": "2025-11-24",
        "document_date": "2025-11-24",
    }


def archive():
    kwame, nadia = person("Kwame Boateng"), person("Nadia Haddad", role="Solution Consultant")
    priya = person("Priya Nair", org="Acme Org", role="IT Lead")
    return [
        statement(1, kwame, "I can purge the landing zone.", "Kwame Boateng can purge it."),
        statement(
            2,
            priya,
            "Ask Kwame, or write to k.boateng@relexsolutions.example.",
            "Priya sends the request to Kwame.",
            agreed_by=[person("Kwame Boateng")],
        ),
        statement(3, nadia, "Nadia here. It is fine.", "Nadia Haddad agrees."),
        statement(4, priya, "Not Nadia Öberg, the other one. Nadia Haddad, employee four."),
        statement(5, priya, "Thanks, Boateng, that helps.", "Boateng helped."),
        statement(
            6,
            nadia,
            "Yes.",
            "Nadia Haddad accepted.",
            agreed_by=[person("Priya Nair", "Acme Org", "IT Lead")],
        ),
    ]


def text_of(statements):
    return json.dumps(statements, ensure_ascii=False)


def test_a_full_name_is_replaced_in_every_field_the_name_sits_in():
    result, receipt = delete_person(archive(), "Kwame Boateng")
    placeholder = PLACEHOLDERS["relex"]
    assert result[0]["actor"]["name"] == placeholder
    assert result[0]["claim"] == f"{placeholder} can purge it."
    assert result[1]["agreed_by"][0]["name"] == placeholder
    assert "Boateng" not in text_of(result) and "Kwame" not in text_of(result)
    assert receipt["deleted"]["placeholder"] == placeholder


def test_the_quoted_words_are_redacted_too_including_emails_and_bare_names():
    result, _ = delete_person(archive(), "Kwame Boateng")
    placeholder = PLACEHOLDERS["relex"]
    assert result[1]["verbatim_span"] == f"Ask {placeholder}, or write to {placeholder}."
    assert result[4]["verbatim_span"] == f"Thanks, {placeholder}, that helps."


def test_the_neighbouring_statements_survive_with_their_ids_and_content():
    before = archive()
    result, receipt = delete_person(before, "Kwame Boateng")
    assert [s["id"] for s in result] == [s["id"] for s in before]
    assert result[2] == before[2]
    assert receipt["deleted"]["statements_changed"] == 3
    assert result[0]["speech_act"] == "report" and result[0]["actor"]["role"] == "Consultant"


def test_the_input_is_left_as_it_was():
    before = archive()
    snapshot = copy.deepcopy(before)
    delete_person(before, "Kwame Boateng")
    assert before == snapshot


def test_a_person_from_the_customer_gets_the_customer_placeholder():
    result, receipt = delete_person(archive(), "Priya Nair")
    assert receipt["deleted"]["placeholder"] == PLACEHOLDERS["customer"]
    assert result[5]["agreed_by"][0]["name"] == PLACEHOLDERS["customer"]


def test_a_partner_gets_the_partner_placeholder():
    partner = person("Ruth Oyelaran", org="Meridian Consulting", role="Advisor")
    _, receipt = delete_person([statement(1, partner, "We can help.")], "Ruth Oyelaran")
    assert receipt["deleted"]["placeholder"] == PLACEHOLDERS["partner"]


def test_two_spellings_of_one_person_are_one_person():
    henrik = [
        statement(1, person("Henrik Sørensen", role="Account Director"), "It is my account."),
        statement(
            2,
            person("Priya Nair", "Acme Org"),
            "Henrik Sorensen said henrik.sorensen@relexsolutions.example.",
        ),
        statement(3, person("Priya Nair", "Acme Org"), "Sørensen, Henrik will call."),
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
    assert "Nadia Öberg" in result[3]["verbatim_span"]
    assert "Haddad" not in text_of(result)


def test_a_first_name_shared_with_someone_else_is_left_alone_and_the_receipt_says_so():
    result, receipt = delete_person(archive(), "Nadia Haddad")
    assert result[2]["verbatim_span"] == "Nadia here. It is fine."
    assert any("Nadia" in item and "Nadia Öberg" in item for item in receipt["left_in_place"])


def test_the_exact_full_name_beats_a_first_name_pick():
    result, receipt = delete_person(archive(), "Nadia Öberg")
    assert receipt["deleted"]["name"] == "Nadia Öberg"
    assert receipt["deleted"]["placeholder"] == PLACEHOLDERS["unknown"]
    assert result[3]["verbatim_span"].startswith("Not [former participant]")
    assert result[2] == archive()[2] and result[5]["actor"]["name"] == "Nadia Haddad"


def test_a_name_nobody_has_changes_nothing_and_says_so():
    before = archive()
    result, receipt = delete_person(before, "Zoe Nobody")
    assert result == before
    assert receipt["deleted"] is None


def test_a_speaker_the_file_does_not_name_is_never_a_person():
    unnamed = {
        "name": "Guest 1",
        "label": "Guest 1",
        "organization": "Not stated",
        "role": "Not stated",
    }
    before = [statement(1, unnamed, "Hello."), *archive()]
    result, _ = delete_person(before, "Guest 1")
    assert result == before


def test_ids_and_dates_are_never_swept():
    kwame = person("Kwame Boateng")
    odd = statement(1, kwame, "Hello.")
    odd["document_id"] = "transcripts/kwame-boateng-notes"
    result, _ = delete_person([odd], "Kwame Boateng")
    assert result[0]["document_id"] == "transcripts/kwame-boateng-notes"


def test_a_second_deletion_of_the_same_person_finds_nobody():
    once, _ = delete_person(archive(), "Kwame Boateng")
    twice, receipt = delete_person(once, "Kwame Boateng")
    assert twice == once and receipt["deleted"] is None


def test_phone_numbers_are_reported_as_not_covered():
    talker = statement(1, person("Kwame Boateng"), "Call +351 913 882 145.")
    _, receipt = delete_person([talker, *archive()[2:]], "Kwame Boateng")
    assert any("phone" in item for item in receipt["left_in_place"])

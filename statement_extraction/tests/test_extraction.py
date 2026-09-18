from src.app.documents import parse_document
from src.app.extraction import SYSTEM_PROMPT, _batches, extract_document

TEAMS = """*** SYNTHETIC DATA.
Meeting: Design workshop
Customer: Acme Org
Date: 2024-11-12
Phase: Implementation
Attendees: Ann Lee (Acme, Head of Supply Chain), Bo Ray (RELEX)

Bo Ray
0:040:04
BR
Bo Ray 4 seconds
I propose we drop the operator ID field from the extract.
Ann Lee
0:200:20
AL
Ann Lee 20 seconds
Yes, that works for us.
Guest 1
0:300:30
G1
Guest 1 30 seconds
Waste was roughly 3
"""


def statement(**overrides) -> dict:
    item = {
        "unit": 1,
        "span": "I propose we drop the operator ID field from the extract.",
        "claim": "Bo Ray proposed dropping the operator ID field from the extract.",
        "act": "proposal",
        "agreed_by": ["Ann Lee"],
        "org": "RELEX",
        "role": None,
    }
    return item | overrides


def run(*items: dict) -> tuple[list[dict], dict]:
    doc = parse_document(TEAMS, "transcripts/07_design", "transcript")
    records, dropped = extract_document(doc, lambda messages: {"statements": list(items)}, 1000)
    return records, dict(dropped)


def test_a_good_statement_becomes_a_record_with_code_derived_location_and_actor():
    records, dropped = run(statement())
    assert dropped == {}
    assert records == [
        {
            "id": "transcripts/07_design#1",
            "doc_id": "transcripts/07_design",
            "doc_type": "transcript",
            "doc_date": "2024-11-12",
            "stated_on": "2024-11-12",
            "position": "4 seconds",
            "lines": [12, 12],
            "span": "I propose we drop the operator ID field from the extract.",
            "claim": "Bo Ray proposed dropping the operator ID field from the extract.",
            "act": "proposal",
            "actor": {"name": "Bo Ray", "label": None, "org": "RELEX", "role": None},
            "agreed_by": ["Ann Lee"],
        }
    ]


def test_a_span_that_is_not_in_its_unit_is_dropped():
    records, dropped = run(
        statement(span="I suggest we drop the operator ID field from the extract."),
        statement(unit=2),  # the right words, credited to the wrong turn
    )
    assert records == []
    assert dropped == {"span not in the unit": 2}


def test_a_cut_off_number_cannot_be_completed():
    records, dropped = run(statement(unit=3, span="Waste was roughly 3.4%"))
    assert records == []
    assert dropped == {"span not in the unit": 1}


def test_a_unit_number_outside_the_document_is_dropped():
    records, dropped = run(statement(unit=9))
    assert records == []
    assert dropped == {"unit not in this batch": 1}


def test_an_unknown_act_or_an_empty_claim_is_dropped():
    records, dropped = run(statement(act="promise"), statement(claim="  "))
    assert records == []
    assert dropped == {"no claim or unknown act": 2}


def test_the_same_quote_twice_is_kept_once():
    records, dropped = run(statement(), statement(claim="The same thing again."))
    assert len(records) == 1
    assert dropped == {"duplicate": 1}


def test_agreers_who_are_not_in_the_document_are_left_out():
    records, _ = run(statement(agreed_by=["Ann Lee", "Marco Rossi"]))
    assert records[0]["agreed_by"] == ["Ann Lee"]


def test_an_organisation_or_role_the_document_does_not_state_is_null():
    stated, _ = run(statement(org="RELEX", role="Solution Architect"))
    assert stated[0]["actor"]["org"] == "RELEX"
    assert stated[0]["actor"]["role"] is None


def test_a_speaker_the_file_does_not_name_stays_unnamed():
    records, _ = run(statement(unit=3, span="Waste was roughly 3", agreed_by=[], org=None))
    assert records[0]["actor"] == {"name": None, "label": "Guest 1", "org": None, "role": None}


def test_units_are_batched_by_words_and_never_split():
    doc = parse_document(TEAMS, "transcripts/07_design", "transcript")
    assert [list(batch) for batch in _batches(doc.units, 1000)] == [[1, 2, 3]]
    assert [list(batch) for batch in _batches(doc.units, 5)] == [[1], [2], [3]]


def test_the_prompt_tells_the_model_not_to_complete_cut_off_text():
    assert "quote it cut off" in SYSTEM_PROMPT

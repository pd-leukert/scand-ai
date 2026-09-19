from src.app.output import NOT_STATED, to_statement


def record(**overrides) -> dict:
    base = {
        "stated_on": "2025-11-18",
        "position": "message 4 of 4",
        "lines": [93, 94],
        "span": "It must be excluded at source before the next extract runs.",
        "claim": "The speaker wants the field excluded at source.",
        "act": "proposal",
        "handling": "none",
        "actor": {"name": "Priya Nair", "label": None, "org": "Acme Org", "role": "IT Lead"},
        "agreed_by": [],
    }
    return base | overrides


def test_a_record_becomes_the_shape_the_backend_loads():
    assert to_statement(record()) == {
        "claim": "The speaker wants the field excluded at source.",
        "speech_act": "proposal",
        "actor": {
            "name": "Priya Nair",
            "organization": "Acme Org",
        },
        "statement_date": "2025-11-18",
    }


def test_a_speaker_the_file_does_not_name_is_shown_by_the_files_label():
    unnamed = {"name": None, "label": "Guest 1", "org": None, "role": None}
    actor = to_statement(record(actor=unnamed))["actor"]
    assert actor == {
        "name": "Guest 1",
        "organization": NOT_STATED,
    }


def test_what_no_document_states_is_not_stated_never_guessed():
    actor = {"name": "Kwame Boateng", "label": None, "org": None, "role": None}
    shown = to_statement(record(actor=actor))["actor"]
    assert shown["organization"] == NOT_STATED

from src.app.output import NOT_STATED, to_statement


def record(**overrides) -> dict:
    base = {
        "id": "emails/07#4",
        "doc_id": "emails/07",
        "doc_type": "email",
        "doc_date": "2025-11-24",
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
        "id": "emails/07#4",
        "document_id": "emails/07",
        "doc_type": "email",
        "location": {"page": None, "line_start": 93, "line_end": 94},
        "position": "message 4 of 4",
        "verbatim_span": "It must be excluded at source before the next extract runs.",
        "claim": "The speaker wants the field excluded at source.",
        "speech_act": "proposal",
        "handling": "none",
        "actor": {
            "name": "Priya Nair",
            "label": None,
            "organization": "Acme Org",
            "role": "IT Lead",
        },
        "agreed_by": [],
        "statement_date": "2025-11-18",
        "document_date": "2025-11-24",
    }


def test_a_speaker_the_file_does_not_name_is_shown_by_the_files_label():
    unnamed = {"name": None, "label": "Guest 1", "org": None, "role": None}
    actor = to_statement(record(actor=unnamed))["actor"]
    assert actor == {
        "name": "Guest 1",
        "label": "Guest 1",
        "organization": NOT_STATED,
        "role": NOT_STATED,
    }


def test_what_no_document_states_is_not_stated_never_guessed():
    actor = {"name": "Kwame Boateng", "label": None, "org": None, "role": None}
    shown = to_statement(record(actor=actor))["actor"]
    assert (shown["organization"], shown["role"]) == (NOT_STATED, NOT_STATED)
    assert shown["label"] is None


def test_an_agreement_keeps_who_agreed_and_where():
    agreed = {
        "name": "Nadia Haddad",
        "label": None,
        "org": "RELEX",
        "role": None,
        "statement": "emails/07#9",
    }
    [entry] = to_statement(record(agreed_by=[agreed]))["agreed_by"]
    assert entry == {
        "name": "Nadia Haddad",
        "label": None,
        "organization": "RELEX",
        "role": NOT_STATED,
        "statement": "emails/07#9",
    }

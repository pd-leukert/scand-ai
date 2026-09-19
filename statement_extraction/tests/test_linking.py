from src.app.extraction import LOOKAHEAD, link_agreements


def record(n: int, who: str | None, act: str, span: str, *, message: int | None = None, label=None):
    """A statement as the extraction step writes it. A message number makes it an email."""
    return {
        "id": f"doc#{n}",
        "doc_type": "email" if message else "transcript",
        "position": f"message {message} of 4" if message else f"{n} seconds",
        "lines": [n, n],
        "stated_on": "2025-11-20",
        "span": span,
        "act": act,
        "actor": {"name": who, "label": label, "org": None, "role": None},
        "agreed_by": [],
    }


def answering(response: str, by: str, quote: str):
    """A model that always gives the same answer, and remembers what it was shown."""
    seen: list[str] = []

    def chat(messages, schema=None):
        seen.append(messages[1]["content"])
        return {"response": response, "by": by, "quote": quote}

    chat.seen = seen
    return chat


PROPOSAL = "It must be excluded at source before the next extract runs."
REPLY = "Confirmed. OP_ID is dropped at the extract from the next run."


def thread():
    # A thread lists the newest message first: message 4 is the oldest.
    return [
        record(1, "Nadia", "report", REPLY, message=3),
        record(2, "Priya", "proposal", PROPOSAL, message=4),
    ]


def test_a_verified_response_fills_agreed_by_with_the_agreeing_statement():
    records = thread()
    counts = link_agreements(records, answering("accepted", "Nadia", "Confirmed. OP_ID is dropped"))
    assert counts == {"accepted": 1}
    assert records[1]["agreed_by"] == [{"name": "Nadia", "label": None, "statement": "doc#1"}]
    assert records[0]["agreed_by"] == []


def test_a_response_quoted_from_words_the_person_never_said_is_ignored():
    records = thread()
    counts = link_agreements(records, answering("accepted", "Nadia", "Yes, I agree entirely"))
    assert counts == {"response not found in the text": 1}
    assert records[1]["agreed_by"] == []


def test_a_response_credited_to_someone_who_did_not_say_it_is_ignored():
    records = thread()
    counts = link_agreements(records, answering("accepted", "Kwame", "Confirmed. OP_ID is dropped"))
    assert counts == {"response not found in the text": 1}
    assert records[1]["agreed_by"] == []


def test_no_response_leaves_nobody_agreeing():
    records = thread()
    assert link_agreements(records, answering("none", "", "")) == {"no response": 1}
    assert records[1]["agreed_by"] == []


def test_a_rejection_is_counted_but_does_not_count_as_agreement():
    records = thread()
    counts = link_agreements(records, answering("rejected", "Nadia", "Confirmed. OP_ID is dropped"))
    assert counts == {"rejected": 1}
    assert records[1]["agreed_by"] == []


def test_only_later_statements_by_other_people_are_shown():
    records = thread() + [record(3, "Priya", "report", "Thanks.", message=1)]
    chat = answering("none", "", "")
    link_agreements(records, chat)
    shown = chat.seen[0]
    assert REPLY in shown  # Nadia answered after the proposal
    assert "Thanks." not in shown  # Priya's own later statement is not an answer
    assert PROPOSAL not in shown.split("Statements after it")[1]  # nothing earlier is shown


def test_a_transcript_runs_forward_so_the_reply_is_the_next_turn():
    records = [
        record(10, "Bo", "proposal", "Let us drop the field."),
        record(20, "Ann", "agreement", "Yes, that works for us."),
    ]
    counts = link_agreements(records, answering("accepted", "Ann", "that works for us"))
    assert counts == {"accepted": 1}
    assert records[0]["agreed_by"][0]["name"] == "Ann"


def test_speakers_the_file_does_not_name_can_still_agree_by_label():
    records = [
        record(10, None, "proposal", "Do not schedule him on a Friday.", label="Them"),
        record(20, None, "agreement", "Noted.", label="Me"),
    ]
    link_agreements(records, answering("accepted", "Me", "Noted."))
    assert records[0]["agreed_by"] == [{"name": None, "label": "Me", "statement": "doc#20"}]


def test_reports_and_agreements_are_not_asked_about():
    records = [record(1, "Bo", "report", "Done."), record(2, "Ann", "agreement", "Yes.")]
    chat = answering("accepted", "Ann", "Yes.")
    assert link_agreements(records, chat) == {}
    assert chat.seen == []


def test_only_the_next_few_later_statements_are_shown():
    records = [record(1, "Bo", "proposal", "Do it.")]
    records += [record(n + 1, "Ann", "report", f"Reply number {n}.") for n in range(1, 20)]
    chat = answering("none", "", "")
    link_agreements(records, chat)
    assert chat.seen[0].count("[Ann") == LOOKAHEAD

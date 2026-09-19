import os
from pathlib import Path

import pytest
from src.app.documents import Document, load_corpus, parse_document, parse_sent_date

CORPUS = Path(os.environ.get("CORPUS_DIR", Path(__file__).parents[2] / "input"))

TEAMS = """*** SYNTHETIC DATA.
Meeting: Kickoff
Customer: Acme Org
Date: 2024-03-20
Phase: Pre-Sales
Attendees: Ann Lee (Acme), Bo Ray (RELEX), Cy Doe (Acme CFO, joins late)

Ann Lee
0:040:04
AL
Ann Lee 4 seconds
Hello all.
Bo Ray
1:041:04
BR
Bo Ray 1 minute 4 seconds
We need it in 30 seconds
Bo Ray 1 minute 27 seconds
then done.
"""

INTERNAL = """*** SYNTHETIC DATA.
Meeting: Handover
Customer: Acme Org
Date: 2024-07-09
Phase: Implementation
Attendees: Bo Ray (RELEX), Di Fox (RELEX)

Me: So this is the handover.
Them: A lot, honestly.
Them: More than the SOW says.
"""

THREAD = """*** SYNTHETIC DATA.

Subject: Field exclusion
From: Ann Lee <ann@acme.example>
Date: Monday, November 24, 2025 17:55
To: Bo Ray <bo@relex.example>
Messages in thread: 2

This email originated from outside of RELEX. Be careful.

Three at Meridian.

Ann Lee
IT Lead


From: Bo Ray <bo@relex.example>
Gesendet: Mittwoch, 19. November 2025 11:44
An: Ann Lee <ann@acme.example>
Betreff: Re: Field exclusion

Confirmed.
"""


def test_teams_turns_carry_names_and_elapsed_positions():
    doc = parse_document(TEAMS, "transcripts/x", "transcript")
    assert doc.doc_date == "2024-03-20"
    assert doc.attendees == {"Ann Lee": "Acme", "Bo Ray": "RELEX", "Cy Doe": "Acme CFO, joins late"}
    assert [unit.name for unit in doc.units] == ["Ann Lee", "Bo Ray"]
    assert [(line.no, line.text, line.position) for line in doc.units[1].lines] == [
        (17, "We need it in 30 seconds", "1 minute 4 seconds"),
        (19, "then done.", "1 minute 27 seconds"),
    ]


def test_speakers_the_file_does_not_name_are_labels_not_names():
    text = TEAMS + "Guest 1\n2:002:00\nG1\nGuest 1 2 minutes\nPut it in writing.\n"
    text += "+358 40 5512 097\n2:302:30\n+3\n+358 40 5512 097 2 minutes 30 seconds\nMm-hm.\n"
    doc = parse_document(text, "transcripts/x", "transcript")
    assert [(unit.name, unit.label) for unit in doc.units[2:]] == [
        (None, "Guest 1"),
        (None, "+358 40 5512 097"),
    ]
    assert doc.units[3].lines[0].position == "2 minutes 30 seconds"


def test_internal_transcript_has_labels_and_no_names():
    doc = parse_document(INTERNAL, "transcripts/y", "transcript")
    assert [(unit.name, unit.label) for unit in doc.units] == [(None, "Me"), (None, "Them")]
    assert [line.text for line in doc.units[1].lines] == [
        "A lot, honestly.",
        "More than the SOW says.",
    ]
    assert doc.units[1].lines[0].position == "line 9"


def test_thread_messages_count_from_the_top_and_drop_the_banner():
    doc = parse_document(THREAD, "emails/z", "email")
    assert doc.doc_date == "2025-11-24"
    assert [(unit.name, unit.sent) for unit in doc.units] == [
        ("Ann Lee", "2025-11-24"),
        ("Bo Ray", "2025-11-19"),
    ]
    assert [line.text for line in doc.units[0].lines] == [
        "Three at Meridian.",
        "Ann Lee",
        "IT Lead",
    ]
    assert doc.units[1].lines[0].position == "message 2 of 2"


def test_thread_with_a_wrong_declared_count_fails_loudly():
    with pytest.raises(ValueError, match="header says 3 messages, found 2"):
        parse_document(THREAD.replace("thread: 2", "thread: 3"), "emails/z", "email")


@pytest.mark.parametrize(
    ("raw", "iso"),
    [
        ("Monday, November 24, 2025 17:55", "2025-11-24"),
        ("Wednesday, February 5, 2025 9:30 AM", "2025-02-05"),
        ("Mittwoch, 22. Januar 2025 08:50", "2025-01-22"),
        ("den 20 augusti 2024 09:05", "2024-08-20"),
    ],
)
def test_parse_sent_date(raw: str, iso: str):
    assert parse_sent_date(raw) == iso


@pytest.fixture(scope="module")
def corpus() -> list[Document]:
    if not CORPUS.is_dir():
        pytest.skip(f"no corpus at {CORPUS}; set CORPUS_DIR")
    return load_corpus(CORPUS)


def test_corpus_has_the_documents_the_readme_lists(corpus: list[Document]):
    counts = {
        kind: sum(doc.doc_type == kind for doc in corpus)
        for kind in ("transcript", "email", "report")
    }
    assert counts == {"transcript": 23, "email": 20, "report": 2}
    assert sum(len(doc.units) for doc in corpus if doc.doc_type != "transcript") == 135


def test_every_line_number_points_at_that_line_in_the_file(corpus: list[Document]):
    for doc in corpus:
        source = (CORPUS / f"{doc.doc_id}.txt").read_text(encoding="utf-8-sig").split("\n")
        for unit in doc.units:
            for line in unit.lines:
                assert line.text in source[line.no - 1], (doc.doc_id, line.no)


def test_every_unit_has_text_and_a_position(corpus: list[Document]):
    for doc in corpus:
        assert doc.units, doc.doc_id
        for unit in doc.units:
            assert unit.lines, (doc.doc_id, unit.name)
            assert all(line.position for line in unit.lines), doc.doc_id


def test_internal_transcripts_record_labels_not_names(corpus: list[Document]):
    internal = [doc for doc in corpus if "INTERNAL" in doc.doc_id]
    assert len(internal) == 3
    for doc in internal:
        assert all(unit.name is None and unit.label in {"Me", "Them"} for unit in doc.units)


def test_named_teams_speakers_are_attendees(corpus: list[Document]):
    strangers = {
        unit.name
        for doc in corpus
        if doc.doc_type == "transcript"
        for unit in doc.units
        if unit.name is not None and unit.name not in doc.attendees
    }
    # Transcript 03 spells Henrik Sørensen without the ø in two turns. Deletion has to cope.
    assert strangers == {"Henrik Sorensen"}


def test_thread_messages_run_newest_first(corpus: list[Document]):
    for doc in corpus:
        if doc.doc_type != "transcript":
            sent = [unit.sent for unit in doc.units]
            assert sent == sorted(sent, reverse=True), doc.doc_id

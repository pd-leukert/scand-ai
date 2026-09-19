import re
from dataclasses import dataclass
from pathlib import Path

_MONTH_NAMES = [
    "january february march april may june july august september october november december",
    "januar februar märz april mai juni juli august september oktober november dezember",
    "januari februari mars april maj juni juli augusti september oktober november december",
]
MONTHS = {name: i + 1 for names in _MONTH_NAMES for i, name in enumerate(names.split())}

_EN_DATE = re.compile(r"(\w+) (\d{1,2}), (\d{4})")
_DAY_FIRST_DATE = re.compile(r"(\d{1,2})\.? (\w+) (\d{4})")

_TRANSCRIPT_KEY = re.compile(r"(Meeting|Customer|Date|Phase|Attendees): (.*)")
_DOUBLED_TIME = re.compile(r"(\d+:\d{2}(?::\d{2})?)\1")
_ELAPSED = r"\d+ (?:hours?|minutes?|seconds?)(?: \d+ (?:minutes?|seconds?))*"
_SEGMENT = re.compile(rf"(.+?) ({_ELAPSED})")
_ANONYMOUS = re.compile(r"Unknown Speaker|Guest \d+|\+?\d[\d ]{6,}")
_INTERNAL_LINE = re.compile(r"(Me|Them): ?(.*)")

_FROM = re.compile(r"(?:From|Von|Från): (.*)")
_SENT = re.compile(r"(?:Sent|Gesendet|Skickat|Date): (.*)")
_SUBJECT = re.compile(r"(?:Subject|Betreff|Ämne):.*")
_SUBJECT_TEXT = re.compile(r"(?:Subject|Betreff|Ämne): ?(.*)")
_THREAD_COUNT = re.compile(r"Messages in thread: (\d+)")
_SENDER_NAME = re.compile(r"(.+?)\s*<")
_BANNER = "This email originated from outside of RELEX"

_DOC_TYPES = {"transcripts": "transcript", "emails": "email", "reports": "report"}


@dataclass(frozen=True)
class Line:
    no: int  # 1-indexed line in the source file
    text: str
    position: str  # as a person finds it in the file: elapsed time, "message n of N" or "line n"


@dataclass
class Unit:
    """One speaker turn or one message. A statement never spans two units."""

    name: str | None
    # What the file calls a speaker it does not name: "Me" or "Them" in the INTERNAL
    # transcripts, "Unknown Speaker" or "Guest 1" or a dial-in number in the Teams ones.
    label: str | None
    sent: str | None  # ISO date, messages only
    lines: list[Line]

    @property
    def speaker(self) -> str | None:
        return self.name or self.label


@dataclass
class Document:
    doc_id: str
    doc_type: str
    doc_date: str
    # The document's own summary of itself, taken from its first few lines: the transcript
    # header's Meeting line, or a thread's Subject line. Never written by extraction, only
    # read off the file, so it carries no more risk of invention than the rest of the header.
    summary: str
    meta: dict[str, str]
    attendees: dict[str, str]  # name -> the parenthesised note in the header, e.g. "Acme CFO"
    units: list[Unit]


def parse_sent_date(raw: str) -> str:
    """ISO date from an Outlook date in English, German or Swedish."""
    if m := _EN_DATE.search(raw):
        month, day, year = m.groups()
    elif m := _DAY_FIRST_DATE.search(raw):
        day, month, year = m.groups()
    else:
        raise ValueError(f"unrecognised date: {raw!r}")
    return f"{int(year):04d}-{MONTHS[month.lower()]:02d}-{int(day):02d}"


def load_document(path: Path, corpus: Path) -> Document:
    relative = path.relative_to(corpus)
    doc_type = _DOC_TYPES[relative.parts[0]]
    text = path.read_text(encoding="utf-8-sig")
    return parse_document(text, relative.with_suffix("").as_posix(), doc_type)


def load_corpus(corpus: Path) -> list[Document]:
    return [
        load_document(path, corpus)
        for folder in _DOC_TYPES
        for path in sorted((corpus / folder).glob("*.txt"))
    ]


def parse_document(text: str, doc_id: str, doc_type: str) -> Document:
    # split("\n"), not splitlines(): line numbers must match what an editor shows.
    lines = text.split("\n")
    try:
        if doc_type == "transcript":
            meta, start = _parse_transcript_header(lines)
            first = next((line for line in lines[start:] if line.strip()), "")
            if _INTERNAL_LINE.match(first):
                units = _parse_internal(lines, start)
            else:
                units = _parse_teams(lines, start)
            return Document(
                doc_id,
                doc_type,
                meta["Date"],
                meta.get("Meeting", ""),
                meta,
                _parse_attendees(meta["Attendees"]),
                units,
            )
        units, subject = _parse_thread(lines)
        # A thread has no attendee header, so "who's involved" is whoever actually sent a
        # message — the same set a person skimming the file would arrive at.
        people = dict.fromkeys((unit.name for unit in units if unit.name), "")
        return Document(doc_id, doc_type, units[0].sent, subject, {}, people, units)
    except ValueError as error:
        raise ValueError(f"{doc_id}: {error}") from error


def _parse_transcript_header(lines: list[str]) -> tuple[dict[str, str], int]:
    meta: dict[str, str] = {}
    for i, line in enumerate(lines):
        if m := _TRANSCRIPT_KEY.fullmatch(line.strip()):
            meta[m[1]] = m[2].strip()
            if m[1] == "Attendees":
                return meta, i + 1
    raise ValueError("no Attendees line in the transcript header")


def _parse_attendees(value: str) -> dict[str, str]:
    attendees = {}
    # Split on commas that are not inside parentheses: "Robert Kahn (Acme CFO, joins late)".
    for part in re.split(r",\s*(?![^()]*\))", value):
        m = re.fullmatch(r"(.+?)\s*(?:\((.*)\))?", part.strip())
        attendees[m[1]] = m[2] or ""
    return attendees


def _segment(line: str, speakers: set[str]) -> tuple[str, str] | None:
    # A text line can end in "30 seconds" too, so the name has to be a known speaker.
    m = _SEGMENT.fullmatch(line)
    return (m[1], m[2]) if m and m[1] in speakers else None


def _teams_unit(speaker: str) -> Unit:
    if _ANONYMOUS.fullmatch(speaker):
        return Unit(None, speaker, None, [])
    return Unit(speaker, None, None, [])


def _parse_teams(lines: list[str], start: int) -> list[Unit]:
    speakers = {
        lines[i].strip()
        for i in range(start, len(lines) - 1)
        if _DOUBLED_TIME.fullmatch(lines[i + 1].strip())
    }
    units: list[Unit] = []
    position = ""
    i = start
    while i < len(lines):
        line = lines[i].strip()
        if i + 1 < len(lines) and _DOUBLED_TIME.fullmatch(lines[i + 1].strip()):
            # A turn starts with four lines: name, doubled time, initials, "name elapsed".
            header = lines[i + 3].strip() if i + 3 < len(lines) else ""
            segment = _segment(header, speakers)
            if segment is None or segment[0] != line:
                raise ValueError(f"line {i + 4}: expected '{line} <elapsed>', got {header!r}")
            units.append(_teams_unit(line))
            position = segment[1]
            i += 4
        elif segment := _segment(line, speakers):
            if not units or units[-1].speaker != segment[0]:
                units.append(_teams_unit(segment[0]))
            position = segment[1]
            i += 1
        else:
            if line:
                if not units:
                    raise ValueError(f"line {i + 1}: text before the first speaker")
                units[-1].lines.append(Line(i + 1, line, position))
            i += 1
    return [unit for unit in units if unit.lines]


def _parse_internal(lines: list[str], start: int) -> list[Unit]:
    units: list[Unit] = []
    for i in range(start, len(lines)):
        text = lines[i].strip()
        if not text:
            continue
        position = f"line {i + 1}"
        if m := _INTERNAL_LINE.fullmatch(text):
            if not units or units[-1].label != m[1]:
                units.append(Unit(None, m[1], None, []))
            units[-1].lines.append(Line(i + 1, m[2], position))
        elif units:
            units[-1].lines.append(Line(i + 1, text, position))
        else:
            raise ValueError(f"line {i + 1}: text before the first speaker")
    return units


def _parse_thread(lines: list[str]) -> tuple[list[Unit], str]:
    starts = [i for i, line in enumerate(lines) if _FROM.fullmatch(line.strip())]
    declared = next(
        (int(m[1]) for line in lines if (m := _THREAD_COUNT.fullmatch(line.strip()))), None
    )
    if declared != len(starts):
        raise ValueError(f"header says {declared} messages, found {len(starts)}")

    # The topmost message is the newest (threads run reverse-chronological), so its Subject
    # line is the first one in the file — the summary this document opens with.
    subject = next((m[1].strip() for line in lines if (m := _SUBJECT_TEXT.match(line.strip()))), "")

    units = []
    for n, start in enumerate(starts, 1):
        # The header ends at the subject line, or at the message count in the first message.
        end = next(
            i
            for i in range(start, len(lines))
            if _SUBJECT.fullmatch(lines[i].strip()) or _THREAD_COUNT.fullmatch(lines[i].strip())
        )
        sent = next(m[1] for i in range(start, end) if (m := _SENT.fullmatch(lines[i].strip())))
        sender = _FROM.fullmatch(lines[start].strip())[1]
        name = m[1] if (m := _SENDER_NAME.match(sender)) else sender.strip()
        stop = starts[n] if n < len(starts) else len(lines)
        position = f"message {n} of {len(starts)}"
        body = [
            Line(i + 1, lines[i].strip(), position)
            for i in range(end + 1, stop)
            if lines[i].strip() and not lines[i].startswith(_BANNER)
        ]
        units.append(Unit(name, None, parse_sent_date(sent), body))
    return units, subject

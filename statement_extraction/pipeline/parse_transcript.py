"""Deterministic parser for Teams-export meeting transcripts.

Splits a transcript into one segment per timestamped utterance. Everything
here is regex/structure-derived from the file itself (speaker, timestamp,
line numbers) -- nothing here should ever need an LLM, and the citation
fields (position.index / position.timestamp / position.line_range) must be
exact since provenance grading checks "a position in the conversation, not
just the filename."

Format quirks handled (see acme/00_README.md and by inspection):
  - A "full" speaker turn is a 4-line header:
        <Name>
        <M:SS repeated twice with no separator, e.g. "3:133:13">
        <Initials, e.g. "LF">
        <Name> <N> minutes [<S> seconds]
    followed by one or more text lines.
  - A same-speaker continuation after a pause is just the readable
    timestamp line ("<Name> <N> minutes [<S> seconds]") with no header,
    followed by more text. This parser treats each readable-timestamp line
    (full header or continuation) as the start of its own segment, since
    each one carries its own exact timestamp -- that is the finer-grained
    and more precise citation unit.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import registry

DOUBLED_TS_RE = re.compile(r"^(\d{1,2}:\d{1,2})\1$")
INITIALS_RE = re.compile(r"^[A-Z]{1,4}\d*$")
MARKER_RE = re.compile(
    r"^(?P<speaker>.+?) (?P<mins>\d+) minutes?(?: (?P<secs>\d+) seconds?)?$"
)

HEADER_FIELD_RE = re.compile(r"^(Meeting|Customer|Date|Phase|Attendees):\s*(.*)$")


def _parse_header(lines: list[str]) -> tuple[dict[str, str], int]:
    """Return (header fields, index of first content line)."""
    fields: dict[str, str] = {}
    content_start = 0
    for i, line in enumerate(lines):
        m = HEADER_FIELD_RE.match(line.strip())
        if m:
            fields[m.group(1)] = m.group(2).strip()
        if "Attendees" in fields and line.strip() == "" and i > 0:
            content_start = i + 1
            break
    else:
        content_start = len(lines)
    return fields, content_start


def _parse_attendees(raw: str) -> list[str]:
    # "Lena Fischer (Acme), Priya Nair (Acme), Ana Duarte (RELEX PM), Tomas Lindholm (RELEX)"
    names = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        chunk = re.sub(r"\s*\(.*?\)\s*$", "", chunk).strip()
        if chunk:
            names.append(chunk)
    return names


def _format_timestamp(mins: str, secs: str | None) -> str:
    s = int(secs) if secs else 0
    return f"{int(mins)}:{s:02d}"


def _find_markers(lines: list[str], content_start: int) -> list[dict[str, Any]]:
    markers = []
    for i in range(content_start, len(lines)):
        m = MARKER_RE.match(lines[i].strip())
        if not m:
            continue
        speaker = m.group("speaker").strip()
        header_start = i
        # Full 4-line header block: Name / doubled-ts / Initials / this line.
        if i - 3 >= content_start:
            name_line = lines[i - 3].strip()
            ts_line = lines[i - 2].strip()
            init_line = lines[i - 1].strip()
            if (
                name_line == speaker
                and DOUBLED_TS_RE.match(ts_line)
                and INITIALS_RE.match(init_line)
            ):
                header_start = i - 3
        markers.append(
            {
                "line_index": i,
                "header_start": header_start,
                "speaker": speaker,
                "timestamp": _format_timestamp(m.group("mins"), m.group("secs")),
            }
        )
    return markers


def parse_transcript(path: Path) -> dict[str, Any]:
    doc_id = path.stem
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    fields, content_start = _parse_header(raw_lines)
    markers = _find_markers(raw_lines, content_start)

    is_internal = "INTERNAL" in path.name.upper()
    participants = _parse_attendees(fields.get("Attendees", ""))

    segments = []
    for idx, marker in enumerate(markers):
        text_start = marker["line_index"] + 1
        text_end = (
            markers[idx + 1]["header_start"] if idx + 1 < len(markers) else len(raw_lines)
        )
        text_lines = [l.strip() for l in raw_lines[text_start:text_end] if l.strip()]
        text = " ".join(text_lines).strip()
        if not text:
            continue

        person = registry.resolve_by_name(marker["speaker"])
        segments.append(
            {
                "segment_id": f"{doc_id}#t{idx:04d}",
                "position": {
                    "type": "turn",
                    "index": idx,
                    "timestamp": marker["timestamp"],
                    # 1-based, inclusive, matching the raw .txt file's own line numbers
                    "line_range": [text_start + 1, text_end],
                },
                "speaker_or_author": person.name if person else marker["speaker"],
                "speaker_org": person.org if person else "Unknown",
                "speaker_resolved": person is not None,
                "recipients": [],
                "effective_date": fields.get("Date"),
                "text": text,
                "contains_image_placeholder": False,  # transcripts never contain image placeholders
            }
        )

    doc_meta = {
        "doc_id": doc_id,
        "doc_type": "transcript",
        "source_path": str(path),
        "doc_date": fields.get("Date"),
        "meeting_title": fields.get("Meeting"),
        "phase": fields.get("Phase"),
        "is_internal": is_internal,
        "participants": participants,
        "thread_id": None,
    }
    return {"doc": doc_meta, "segments": segments}

"""Deterministic parser for Outlook-export email threads.

Each file holds a full thread, reverse chronological, every earlier message
quoted beneath. This splits it back into individual messages: each message
is its own segment with its own real send date (effective_date), which
matters because a quoted message from months earlier keeps its own date --
the file's overall position says nothing about when a given message was
actually sent.

Known quirks handled (see acme/00_README.md):
  - Four different image-placeholder spellings, only in emails, never in
    transcripts: "[Image removed by sender]", "[cid:image001.png]", a bare
    "Image", and the Swedish "Bild borttagen av avsandaren".
  - A recurring external-sender security banner line that is boilerplate,
    not authored content -- stripped out rather than kept as body text.
  - The top/most-recent message uses "Date:"; every quoted message below it
    uses "Sent:" -- both mean the same thing here.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import registry

FROM_LINE_RE = re.compile(r"^From:\s*(.+)$")
NAME_EMAIL_RE = re.compile(r"^(?P<name>[^<]+?)\s*<(?P<email>[^>]+)>\s*$")
SUBJECT_RE = re.compile(r"^Subject:\s*(.*)$")
SENT_DATE_RE = re.compile(r"^(?:Date|Sent):\s*(.+)$")
TO_RE = re.compile(r"^To:\s*(.*)$")
CC_RE = re.compile(r"^Cc:\s*(.*)$")
THREAD_COUNT_RE = re.compile(r"^Messages in thread:\s*(\d+)$")

SECURITY_BANNER = (
    "This email originated from outside of RELEX. Be careful of attachments "
    "and links from unknown senders. Report suspicious emails using the "
    "report button."
)

IMAGE_PLACEHOLDER_RE = re.compile(
    r"\[Image removed by sender\]|\[cid:[^\]]+\]|Bild borttagen av avs[aä]ndaren|^Image$"
)

CLOSING_LINE_RE = re.compile(
    r"^(Best regards|Kind regards|Regards|Thanks|Cheers)[,.]?\s*$", re.IGNORECASE
)

DATE_FORMATS = [
    "%A, %B %d, %Y %I:%M %p",
    "%A, %B %d, %Y %H:%M",
]


def _parse_date(raw: str) -> str | None:
    from datetime import datetime

    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_people_list(raw: str) -> list[dict[str, str | None]]:
    people = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = NAME_EMAIL_RE.match(chunk)
        name = m.group("name").strip() if m else chunk
        email = m.group("email").strip() if m else None
        person = registry.resolve_by_email(email) if email else None
        if person is None:
            person = registry.resolve_by_name(name)
        people.append(
            {
                "name": person.name if person else name,
                "email": email,
                "resolved": person is not None,
            }
        )
    return people


def _split_messages(lines: list[str]) -> list[tuple[int, int]]:
    starts = [i for i, l in enumerate(lines) if FROM_LINE_RE.match(l.strip())]
    bounds = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(lines)
        block_start = 0 if i == 0 else start
        bounds.append((block_start, end))
    return bounds


def _extract_body(lines: list[str], sender_name: str) -> tuple[str, bool]:
    has_image = False
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == SECURITY_BANNER:
            continue
        if IMAGE_PLACEHOLDER_RE.search(stripped):
            has_image = True
            continue
        kept.append(stripped)

    # Trim leading/trailing blank lines, then cut off the signature block:
    # first closing phrase ("Best regards," ...) or a line that is just the
    # sender's own name, whichever comes first.
    while kept and kept[0] == "":
        kept.pop(0)
    cut = len(kept)
    for i, line in enumerate(kept):
        if CLOSING_LINE_RE.match(line) or line.lower() == sender_name.lower():
            cut = i
            break
    body_lines = [l for l in kept[:cut] if l != ""]
    return " ".join(body_lines).strip(), has_image


def _extract_headers(block_lines: list[str]) -> tuple[dict[str, Any], int]:
    fields: dict[str, Any] = {}
    body_start = 0
    for i, line in enumerate(block_lines):
        stripped = line.strip()
        if stripped == "":
            if fields:
                body_start = i + 1
                break
            continue
        for name, rx in (
            ("subject", SUBJECT_RE),
            ("date", SENT_DATE_RE),
            ("to", TO_RE),
            ("cc", CC_RE),
        ):
            m = rx.match(stripped)
            if m:
                fields[name] = m.group(1).strip()
                break
        else:
            m = FROM_LINE_RE.match(stripped)
            if m:
                fields["from"] = m.group(1).strip()
            else:
                mt = THREAD_COUNT_RE.match(stripped)
                if mt:
                    fields["messages_in_thread"] = int(mt.group(1))
                # else: unrecognised header-zone line -- ignore, keep scanning
        body_start = i + 1
    return fields, body_start


def parse_email_thread(path: Path) -> dict[str, Any]:
    doc_id = path.stem
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    message_bounds = _split_messages(raw_lines)

    segments = []
    all_participants: dict[str, str] = {}
    subject = None
    thread_total = None

    for idx, (start, end) in enumerate(message_bounds):
        block = raw_lines[start:end]
        fields, body_offset = _extract_headers(block)

        from_raw = fields.get("from", "")
        m = NAME_EMAIL_RE.match(from_raw)
        sender_name = m.group("name").strip() if m else from_raw
        sender_email = m.group("email").strip() if m else None
        sender = registry.resolve_by_email(sender_email) if sender_email else None
        if sender is None:
            sender = registry.resolve_by_name(sender_name)

        to_people = _parse_people_list(fields.get("to", ""))
        cc_people = _parse_people_list(fields.get("cc", ""))

        for p in to_people + cc_people + [
            {"name": sender.name if sender else sender_name}
        ]:
            all_participants.setdefault(p["name"], p["name"])

        if idx == 0:
            subject = fields.get("subject")
            thread_total = fields.get("messages_in_thread")

        body_text, has_image = _extract_body(block[body_offset:], sender_name)
        effective_date = _parse_date(fields.get("date", "")) if fields.get("date") else None

        if not body_text:
            continue

        segments.append(
            {
                "segment_id": f"{doc_id}#m{idx:04d}",
                "position": {
                    "type": "message",
                    "index": idx,
                    "timestamp": None,
                    "line_range": [start + 1, end],
                },
                "speaker_or_author": sender.name if sender else sender_name,
                "speaker_org": sender.org if sender else "Unknown",
                "speaker_resolved": sender is not None,
                "recipients": [p["name"] for p in to_people + cc_people],
                "effective_date": effective_date,
                "text": body_text,
                "subject": fields.get("subject"),
                "contains_image_placeholder": has_image,
            }
        )

    doc_meta = {
        "doc_id": doc_id,
        "doc_type": "email_thread",
        "source_path": str(path),
        "doc_date": segments[0]["effective_date"] if segments else None,
        "subject": subject,
        "messages_in_thread_header": thread_total,
        "messages_parsed": len(segments),
        "is_internal": False,
        "participants": sorted(all_participants.values()),
        "thread_id": doc_id,
    }
    return {"doc": doc_meta, "segments": segments}

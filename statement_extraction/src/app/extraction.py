from collections import Counter
from collections.abc import Callable

from .documents import Document, Unit
from .matching import find_span

ACTS = ["proposal", "agreement", "decision", "report", "question", "objection"]
HANDLING = ["none", "personal", "confidential"]

SCHEMA = {
    "type": "object",
    "properties": {
        "statements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "unit": {"type": "integer"},
                    "span": {"type": "string"},
                    "claim": {"type": "string"},
                    "act": {"type": "string", "enum": ACTS},
                    "org": {"type": ["string", "null"]},
                    "role": {"type": ["string", "null"]},
                    "handling": {"type": "string", "enum": HANDLING},
                },
                "required": [
                    "unit",
                    "span",
                    "claim",
                    "act",
                    "org",
                    "role",
                    "handling",
                ],
            },
        }
    },
    "required": ["statements"],
}

SYSTEM_PROMPT = """\
You extract statements from one document of a project record. A statement is one thing one \
person asserted, proposed, agreed to, decided, asked, objected to or reported.

The document is a list of numbered units. Each unit is one speaker's turn or one email message.

For every statement, return:
- unit: the number of the unit the statement is in.
- span: the words of the statement, copied exactly from that one unit, character for character. \
Never fix, shorten, complete, paraphrase or join text. If a sentence is cut off, or a number is \
incomplete, quote it cut off. Do not finish it.
- claim: one plain sentence saying what was stated. Use only words and numbers that are in the \
span. Do not add units, currency, dates or names the span does not contain. If the span is \
unclear or garbled, say it is unclear. Use names as written.
- act: proposal (someone floats an idea or asks for something), agreement (someone accepts \
something another person proposed or said), decision (something is settled), report (a fact or \
status is given), question, or objection. An idea floated by one side is a proposal even if it \
sounds firm. Only call something a decision or agreement if the words show it was settled. \
Repeating the previous line is not an agreement.
- org and role: the speaker's organisation and job title, only if the document states them in \
the attendee list or a signature. Copy the words. Otherwise null.
- handling: personal if the statement reveals private details of someone's life, such as health, \
family or personal circumstances. confidential if a speaker asks that it not be shared or \
written down, or it is commercially sensitive, such as terms given to another customer. \
Otherwise none. Judge the statement the request is about, not only the request itself.

Skip fragments. A line that is cut off, garbled, or only echoes the previous line is not a \
statement. Use only the text you are given. Do not use anything you know from elsewhere. Skip \
greetings, filler and small talk. If the text contains no statements, return an empty list.\
"""

LINK_SCHEMA = {
    "type": "object",
    "properties": {
        "response": {"type": "string", "enum": ["accepted", "rejected", "none"]},
        "by": {"type": "string"},
        "quote": {"type": "string"},
    },
    "required": ["response", "by", "quote"],
}

LINK_PROMPT = """\
You read a statement from a project record and the statements that came after it. Decide how the \
people who came after responded to it.

- accepted: a later statement, by someone else, clearly says yes, confirms it, or does what was \
asked.
- rejected: a later statement, by someone else, clearly says no or refuses.
- none: no later statement answers it. Do not guess. Most statements get none.

Return response, by (the name shown before the responding statement, exactly as shown) and quote \
(the exact words of that statement that show it, copied exactly). If the response is none, leave \
by and quote empty. Use only the text you are given.\
"""

# Later statements by other people shown for each one. Replies come soon after.
LOOKAHEAD = 8

# One chat call: messages in, the parsed JSON answer out. The optional schema is what the answer
# must match; it defaults to the extraction schema.
Chat = Callable[..., dict]


def extract_document(
    doc: Document, chat: Chat, batch_words: int
) -> tuple[list[dict], Counter[str]]:
    """Statements for one document, and how many the model returned that we threw away."""
    records: list[dict] = []
    dropped: Counter[str] = Counter()
    seen: set[tuple[int, str]] = set()
    header = _header(doc)
    for batch in _batches(doc.units, batch_words):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": header + _render(doc, batch)},
        ]
        for item in chat(messages)["statements"]:
            unit_no, claim = item["unit"], item["claim"].strip()
            if unit_no not in batch:
                dropped["unit not in this batch"] += 1
                continue
            unit = doc.units[unit_no - 1]
            match = find_span(unit, item["span"])
            if match is None:
                dropped["span not in the unit"] += 1
                continue
            if not claim or item["act"] not in ACTS or item["handling"] not in HANDLING:
                dropped["no claim or unknown act or handling"] += 1
                continue
            if (unit_no, match.text) in seen:
                dropped["duplicate"] += 1
                continue
            seen.add((unit_no, match.text))
            context = _flat(header + " ".join(line.text for line in unit.lines))
            records.append(
                {
                    "id": f"{doc.doc_id}#{len(records) + 1}",
                    "doc_id": doc.doc_id,
                    "doc_type": doc.doc_type,
                    "doc_date": doc.doc_date,
                    "stated_on": unit.sent or doc.doc_date,
                    "position": match.position,
                    "lines": [match.first_line, match.last_line],
                    "span": match.text,
                    "claim": claim,
                    "act": item["act"],
                    "handling": item["handling"],
                    "actor": {
                        "name": unit.name,
                        "label": unit.label,
                        "org": _stated(item["org"], context),
                        "role": _stated(item["role"], context),
                    },
                    "agreed_by": [],
                }
            )
    return records, dropped


def link_agreements(records: list[dict], chat: Chat) -> Counter[str]:
    """Fill agreed_by on each proposal or question from what other people said after it.

    A response counts only if the person it names has a later statement that contains the quoted
    words. Each link carries the id of that statement, so the agreement has a receipt too.
    """
    counts: Counter[str] = Counter()
    ordered = sorted(records, key=_when)
    for i, record in enumerate(ordered):
        if record["act"] not in ("proposal", "question"):
            continue
        later = [r for r in ordered[i + 1 :] if _who(r) != _who(record)][:LOOKAHEAD]
        if not later:
            continue
        shown = "\n".join(
            f"[{_who(r)}, {r['position']}, {r['stated_on']}] {r['span']}" for r in later
        )
        asked = f"Statement, by {_who(record)} ({record['stated_on']}):\n{record['span']}"
        messages = [
            {"role": "system", "content": LINK_PROMPT},
            {
                "role": "user",
                "content": f"{asked}\n\nStatements after it, by other people:\n{shown}",
            },
        ]
        answer = chat(messages, schema=LINK_SCHEMA)
        if answer["response"] == "none":
            counts["no response"] += 1
            continue
        quote = _flat(answer["quote"])
        source = next(
            (r for r in later if _who(r) == answer["by"] and quote and quote in _flat(r["span"])),
            None,
        )
        if source is None:
            counts["response not found in the text"] += 1
        elif answer["response"] == "accepted":
            counts["accepted"] += 1
            actor = source["actor"]
            record["agreed_by"].append({**actor, "statement": source["id"]})
        else:
            counts["rejected"] += 1
    return counts


def _who(record: dict) -> str:
    actor = record["actor"]
    return actor["name"] or actor["label"] or "unknown"


def _when(record: dict) -> tuple[int, ...]:
    """Time order within a document: a thread lists its newest message first."""
    if record["doc_type"] == "transcript":
        return (record["lines"][0],)
    return (-int(record["position"].split()[1]), record["lines"][0])


def _batches(units: list[Unit], batch_words: int) -> list[range]:
    """Consecutive runs of unit numbers (1-based), each about batch_words long."""
    batches: list[range] = []
    start, words = 1, 0
    for number, unit in enumerate(units, 1):
        size = sum(len(line.text.split()) for line in unit.lines)
        if words and words + size > batch_words:
            batches.append(range(start, number))
            start, words = number, 0
        words += size
    batches.append(range(start, len(units) + 1))
    return batches


def _header(doc: Document) -> str:
    lines = [f"Document: {doc.doc_id}", f"Kind: {doc.doc_type}", f"Date: {doc.doc_date}"]
    if doc.attendees:
        people = [f"{name} ({note})" if note else name for name, note in doc.attendees.items()]
        lines.append("Attendees: " + ", ".join(people))
    return "\n".join(lines) + "\n\n"


def _render(doc: Document, batch: range) -> str:
    parts = []
    for number in batch:
        unit = doc.units[number - 1]
        who = unit.name or f"{unit.label} (name not recorded)"
        sent = f", sent {unit.sent}" if unit.sent else ""
        where = unit.lines[0].position
        text = "\n".join(line.text for line in unit.lines)
        parts.append(f"[{number}] {who} - {where}{sent}\n{text}")
    return "\n\n".join(parts)


def _flat(text: str) -> str:
    return " ".join(text.split()).casefold()


def _stated(value: str | None, context: str) -> str | None:
    """Keep an organisation or role only if the document's own words contain it."""
    if value and _flat(value) and _flat(value) in context:
        return " ".join(value.split())
    return None

"""Delete a person from the statements: rewrite the derived file, never filter at query time.

A person is not a string (D19). The request is resolved to one person first, then every spelling
of that person is replaced by a role-class placeholder in every text field, quotes included (D3).
Nothing here reads a source document or calls a model, and nothing keeps the deleted name.

The unit of work is a document block as the file stores it (D36): the document's own `people`
and `summary` are swept exactly like the statements nested under it, because a name survives
in a header just as well as in a claim (D45).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

PLACEHOLDERS = {
    "relex": "[former RELEX employee]",
    "customer": "[former customer employee]",
    "partner": "[former partner employee]",
    "unknown": "[former participant]",
}

# Fields that hold ids, dates and enum labels, never a person's words. Everything else is
# swept, so a field added to the file later is covered by default.
_SKIP_KEYS = {
    "id",
    "document_id",
    "type",
    "doc_type",
    "date",
    "speech_act",
    "handling",
    "position",
    "statement_date",
    "document_date",
}

# What a transcript calls a speaker it does not name — "Me", "Them", "Unknown Speaker",
# "Guest 1", a dial-in number (documents.Unit.label). The file no longer carries the label
# in a field of its own: output._actor folds it into actor.name (D37), so the only way left
# to tell one from a real name is to recognise the shape. Never a person.
_LABEL_WORDS = {"me", "them", "unknown speaker", "unknown", "guest", "caller", "participant"}
_NUMBERED_LABEL = re.compile(r"^(?:guest|caller|participant|speaker|unknown speaker)\s*\d+$")
_DIAL_IN = re.compile(r"^[\d\s+()-]+$")
_LETTERS = r"[^\W\d_]+"
_PAIR = re.compile(rf"\b({_LETTERS})\s+(?=({_LETTERS})\b)")
_PHONE = re.compile(r"\+?\d[\d ]{8,}\d")
_ONE_FOR_ONE = str.maketrans({"ø": "o", "đ": "d", "ł": "l", "ð": "d"})


@dataclass
class Person:
    key: str
    spellings: Counter = field(default_factory=Counter)
    evidence: int = 0

    @property
    def tokens(self) -> list[str]:
        return self.key.split()

    @property
    def name(self) -> str:
        return self.spellings.most_common(1)[0][0] if self.spellings else self.key.title()


def delete_person(documents: list[dict], request: str) -> tuple[list[dict], dict]:
    """The documents with one person redacted, and a receipt saying who was and was not.

    Takes the file's `documents` array as it is stored (D36) and returns one of the same shape.
    The input is not changed. A request that matches nobody returns the documents as they were.
    """
    people = _find_people(documents)
    tokens = _fold(unicodedata.normalize("NFC", request)).split()
    chosen, others = _resolve(people, tokens, documents)
    receipt: dict = {"requested": request, "deleted": None, "considered": [], "left_in_place": []}
    if chosen is None:
        receipt["considered"] = [_entry(p, "left") for p in others]
        return documents, receipt

    rest = [p for p in people.values() if p.key != chosen.key]
    placeholder = PLACEHOLDERS[_role_class(chosen, documents)]
    rules = _rules(chosen, rest, receipt)
    result, replaced = [], 0
    for document in documents:
        new, count = _redact(document, rules, placeholder)
        result.append(new)
        replaced += count
    # Counted over statements, not documents: it is the number a reader checks against the
    # file, and a document header changing is not a statement changing.
    changed = sum(
        _redact(statement, rules, placeholder)[1] > 0 for statement in _statements(documents)
    )
    receipt["deleted"] = {
        "name": chosen.name,
        "spellings": sorted(chosen.spellings),
        "placeholder": placeholder,
        "statements_changed": changed,
        "replacements": replaced,
    }
    receipt["considered"] = [_entry(chosen, "removed")] + [_entry(p, "left") for p in others]
    phones = sum(any(_PHONE.search(s) for s in _strings(st)) for st in _statements(result))
    if phones:
        receipt["left_in_place"].append(
            f"phone numbers, in {phones} statements: nothing ties a number to a person"
        )
    return result, receipt


def _statements(documents: list[dict]):
    """Every statement in the file, in order, regardless of which document holds it."""
    for document in documents:
        yield from document.get("statements", [])


def _actors(documents: list[dict]):
    """Every actor the file names. agreed_by is gone (D37) but is still read if present, so
    a file written before that change resolves the same people it always did."""
    for statement in _statements(documents):
        for who in [statement.get("actor"), *statement.get("agreed_by", [])]:
            if who:
                yield who


def _is_label(name: str) -> bool:
    folded = _fold(" ".join(name.split()))
    return (
        folded in _LABEL_WORDS
        or bool(_NUMBERED_LABEL.match(folded))
        or bool(_DIAL_IN.match(folded.strip()))
    )


def _fold(text: str) -> str:
    """Lowercase and strip accents, one character for one, so positions line up with the text."""
    out = []
    for ch in text:
        base = next(
            (c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)), ch
        )
        lowered = base.lower().translate(_ONE_FOR_ONE)
        out.append(lowered if len(lowered) == 1 else ch)
    return "".join(out)


def _strings(value, key: str | None = None):
    if isinstance(value, str):
        if key not in _SKIP_KEYS:
            yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v, key)


def _find_people(documents: list[dict]) -> dict[str, Person]:
    people: dict[str, Person] = {}

    def add(spelling: str) -> None:
        key = _fold(" ".join(spelling.split()))
        people.setdefault(key, Person(key)).spellings[" ".join(spelling.split())] += 1

    def named(name: str | None) -> bool:
        return bool(name) and not _is_label(name) and len(name.split()) > 1

    for who in _actors(documents):
        if named(who.get("name")):
            add(who["name"])
    # The document header lists who was in the room, which is where a person who never speaks
    # is named (D45) — the same people the actors already give, plus the silent ones.
    for document in documents:
        for name in document.get("people", []):
            if isinstance(name, str) and named(name):
                add(name)
    first_names = {p.tokens[0] for p in people.values()}
    # People who are only mentioned, such as a second Nadia, show up as "First Last" in the text.
    for document in documents:
        for text in _strings(document):
            for m in _PAIR.finditer(unicodedata.normalize("NFC", text)):
                if m[1][0].isupper() and m[2][0].isupper() and _fold(m[1]) in first_names:
                    add(f"{m[1]} {m[2]}")
    for person in people.values():
        pattern = re.compile(r"\b" + r"\s+".join(map(re.escape, person.tokens)) + r"\b")
        person.evidence = sum(
            bool(pattern.search(_fold(unicodedata.normalize("NFC", " ".join(_strings(st))))))
            for st in _statements(documents)
        )
    return people


def _resolve(people: dict[str, Person], tokens: list[str], documents: list[dict]):
    """The person the request means, and the others it could have meant (D19)."""
    if not tokens or _is_label(" ".join(tokens)):
        return None, []
    if len(tokens) > 1:
        chosen = people.get(" ".join(tokens))
        if chosen is None:
            mentioned = re.compile(r"\b" + r"\s+".join(map(re.escape, tokens)) + r"\b")
            hits = sum(
                bool(mentioned.search(_fold(unicodedata.normalize("NFC", " ".join(_strings(st))))))
                for st in _statements(documents)
            )
            if hits:
                chosen = Person(" ".join(tokens), Counter({" ".join(tokens).title(): hits}), hits)
        alike = [
            p
            for p in people.values()
            if (chosen is None or p.key != chosen.key)
            and (p.tokens[0] == tokens[0] or p.tokens[-1] == tokens[-1])
        ]
        return chosen, alike
    matches = sorted(
        (p for p in people.values() if tokens[0] in (p.tokens[0], p.tokens[-1])),
        key=lambda p: (-p.evidence, p.key),
    )
    return (matches[0], matches[1:]) if matches else (None, [])


def _entry(person: Person, outcome: str) -> dict:
    return {"name": person.name, "statements": person.evidence, "outcome": outcome}


def _role_class(person: Person, documents: list[dict]) -> str:
    orgs: Counter = Counter()
    for who in _actors(documents):
        org = who.get("organization")
        if (
            org
            and org != "Not stated"
            and _fold(" ".join((who.get("name") or "").split())) == person.key
        ):
            orgs[org] += 1
    if not orgs:
        return "unknown"
    org = orgs.most_common(1)[0][0].lower()
    return "relex" if "relex" in org else "partner" if "meridian" in org else "customer"


def _rules(person: Person, rest: list[Person], receipt: dict) -> list[tuple[re.Pattern, bool]]:
    """Patterns over folded text, most specific first, and whether a match must be capitalised."""
    first, last = person.tokens[0], person.tokens[-1]
    full = r"\s+".join(map(re.escape, person.tokens))
    domain = r"[a-z0-9-]+(?:\.[a-z0-9-]+)*"
    rules = [
        (re.compile(rf"\b{full}\b"), False),
        (re.compile(rf"\b{re.escape(last)},\s*{re.escape(first)}\b"), False),
        (
            re.compile(
                rf"\b(?:{re.escape(first)}|{re.escape(first[0])})[._-]?{re.escape(last)}@{domain}"
            ),
            False,
        ),
        (re.compile(rf"\b{re.escape(last)}[._-]{re.escape(first)}@{domain}"), False),
    ]
    for word, index in ((last, -1), (first, 0)):
        sharing = [p.name for p in rest if p.tokens[index] == word]
        if sharing:
            receipt["left_in_place"].append(
                f'"{word.title()}" on its own: also the name of {", ".join(sharing)}'
            )
        else:
            rules.append((re.compile(rf"\b{re.escape(word)}\b"), True))
    return rules


def _redact(value, rules, placeholder, key: str | None = None):
    """The value with the person replaced, and how many replacements were made."""
    if isinstance(value, str):
        return _redact_text(value, rules, placeholder) if key not in _SKIP_KEYS else (value, 0)
    if isinstance(value, dict):
        pairs = {k: _redact(v, rules, placeholder, k) for k, v in value.items()}
        return {k: v for k, (v, _) in pairs.items()}, sum(n for _, n in pairs.values())
    if isinstance(value, list):
        items = [_redact(v, rules, placeholder, key) for v in value]
        return [v for v, _ in items], sum(n for _, n in items)
    return value, 0


def _redact_text(text: str, rules, placeholder: str) -> tuple[str, int]:
    plain = unicodedata.normalize("NFC", text)
    folded = _fold(plain)
    taken: list[tuple[int, int]] = []
    for pattern, capitalised in rules:
        for m in pattern.finditer(folded):
            start, end = m.span()
            if capitalised and not plain[start].isupper():
                continue
            if any(start < b and a < end for a, b in taken):
                continue
            taken.append((start, end))
    if not taken:
        return text, 0
    out, position = [], 0
    for start, end in sorted(taken):
        out += [plain[position:start], placeholder]
        position = end
    out.append(plain[position:])
    return "".join(out), len(taken)

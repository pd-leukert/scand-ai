import re
import unicodedata
from dataclasses import dataclass

from .documents import Unit

# A word, or a number with internal separators: "usable", "3.4", "1,200".
_TOKEN = re.compile(r"\w+(?:[.,]\w+)*")


@dataclass(frozen=True)
class Match:
    first_line: int  # 1-indexed lines in the source file
    last_line: int
    position: str  # of the first line
    text: str  # the span as it stands in the source, not as the model wrote it


def find_span(unit: Unit, span: str) -> Match | None:
    """Where the model's quote sits in this unit, or None if it is not there verbatim.

    Only whitespace and Unicode composition may differ. A quote that starts or ends inside a
    word or a number does not count: "3" is not in "3.4".
    """
    wanted = _collapse(span)
    if not wanted:
        return None
    text, owners = _flatten(unit)
    tokens = [(m.start(), m.end()) for m in _TOKEN.finditer(text)]
    start = text.find(wanted)
    while start != -1:
        end = start + len(wanted)
        if not any(a < start < b or a < end < b for a, b in tokens):
            first, last = unit.lines[owners[start]], unit.lines[owners[end - 1]]
            # The same text twice in one unit: the first occurrence.
            return Match(first.no, last.no, first.position, text[start:end])
        start = text.find(wanted, start + 1)
    return None


def _collapse(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def _flatten(unit: Unit) -> tuple[str, list[int]]:
    """The unit's words joined by single spaces, and for each character the line it is on."""
    chars: list[str] = []
    owners: list[int] = []
    for k, line in enumerate(unit.lines):
        for word in unicodedata.normalize("NFC", line.text).split():
            if chars:
                chars.append(" ")
                owners.append(k)
            chars.extend(word)
            owners.extend([k] * len(word))
    return "".join(chars), owners

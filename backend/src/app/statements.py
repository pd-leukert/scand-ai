"""The derived files the answering path can read: the reconciled file by default, or the
statements file it was derived from (ANSWER_SOURCE, see config.py).

Field shape follows docs/data-model.md. Not a schema until the real dataset is in hand
(decisions.md D7) — this is the interim shape the mock files and the answering path agree
on; see decisions.md D20. The reconciled file is the statements grouped by topic, with the
relations between them and a status on each, written by the reconciliation pass (D31). The
statements file is the flat list before that pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SpeechAct = Literal["proposal", "agreement", "decision", "report", "question", "objection"]
Status = Literal["current", "stale", "never-true", "disputed", "unresolved"]
RelationKind = Literal["supersedes", "corrects", "conflicts-with", "answers"]
ProblemKind = Literal["reversal", "never-true", "conflict", "unanswered"]


class Location(BaseModel):
    page: int | None = None
    line_start: int
    line_end: int
    # The genre-specific pointer D14 asks for: the utterance offset for a transcript, or
    # "message N of M" for an email thread or report. None for statements without one.
    position: str | None = None


class Actor(BaseModel):
    name: str
    organization: str
    role: str


class Statement(BaseModel):
    id: str
    document_id: str
    location: Location
    verbatim_span: str
    actor: Actor
    agreed_by: list[Actor] = []
    speech_act: SpeechAct
    statement_date: datetime
    document_date: date
    # Worked out by the reconciliation pass from the relations, never from dates. The default
    # keeps a file written before D31 loadable, and "current" is what an unlabelled statement is.
    status: Status = "current"


class StatementsFile(BaseModel):
    statements: list[Statement]


class Relation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # `from` is a keyword, so the field is `source` and the file's `from` is its alias.
    source: str = Field(alias="from")
    to: str
    kind: RelationKind


class Summary(BaseModel):
    text: str
    statements: list[str]


class Topic(BaseModel):
    topic: str
    summary: Summary | None = None
    relations: list[Relation] = []
    statements: list[Statement]


class Problem(BaseModel):
    kind: ProblemKind
    topic: str
    statements: list[str]
    note: str = ""


class ReconciledFile(BaseModel):
    topics: list[Topic]
    problems: list[Problem] = []


@dataclass(frozen=True)
class Record:
    """What the answering path holds: topics for the context, statements indexed by id for
    citation resolution, and for each non-current statement the ids that justify its status.

    A record loaded from the statements file has no topics, no problems and no receipts, and
    reconciled is False: nothing was compared, so no status means anything, and none may be
    shown or sent (CLAUDE.md rule 5).
    """

    topics: list[Topic]
    problems: list[Problem]
    statements: dict[str, Statement]
    receipts: dict[str, list[str]]
    reconciled: bool = True


@lru_cache
def load_record(path: str) -> Record:
    """Load the reconciled file once per process and index it.

    Cached by path: the file is treated as static for the lifetime of the process, same as
    D2 assumes for what goes into the model's context. Deletion, when built, must call
    cache_clear() on this and on load_statements_record, or a deleted name keeps answering out
    of a warm process.
    """
    parsed = ReconciledFile.model_validate(json.loads(Path(path).read_text()))
    statements = {s.id: s for topic in parsed.topics for s in topic.statements}
    return Record(parsed.topics, parsed.problems, statements, _receipts(parsed.topics))


@lru_cache
def load_statements_record(path: str) -> Record:
    """The statements file as a record with no currency information (ANSWER_SOURCE=statements)."""
    parsed = StatementsFile.model_validate(json.loads(Path(path).read_text()))
    return Record([], [], {s.id: s for s in parsed.statements}, {}, reconciled=False)


def _receipts(topics: list[Topic]) -> dict[str, list[str]]:
    """For each stale, never-true or disputed statement, the ids of the statements whose
    relations put it there. This is what lets a citation carry its own justification."""
    receipts: dict[str, list[str]] = {}
    for topic in topics:
        status = {s.id: s.status for s in topic.statements}
        for relation in topic.relations:
            if relation.kind == "supersedes" and status.get(relation.to) == "stale":
                receipts.setdefault(relation.to, []).append(relation.source)
            elif relation.kind == "corrects" and status.get(relation.to) == "never-true":
                receipts.setdefault(relation.to, []).append(relation.source)
            elif relation.kind == "conflicts-with":
                for end, other in ((relation.source, relation.to), (relation.to, relation.source)):
                    if status.get(end) == "disputed":
                        receipts.setdefault(end, []).append(other)
    return receipts

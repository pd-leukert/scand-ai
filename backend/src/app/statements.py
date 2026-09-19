"""The derived files the answering path can read: the reconciled file by default, or the
statements file it was derived from (ANSWER_SOURCE, see config.py).

Field shape follows docs/data-model.md. Not a schema until the real dataset is in hand
(decisions.md D7) — this is the interim shape the mock files and the answering path agree
on; see decisions.md D20. The reconciled file is the statements grouped by topic, with the
relations between them and a status on each, written by the reconciliation pass (D42). The
statements file is the flat list before that pass.

Both files carry what is true of a whole document once, on a `documents` entry, not once per
statement (D36), and carry per statement only claim, actor{name, organization}, speech_act and
statement_date (D37) — plus, in the reconciled file, the status and the id the relations point
at (D46). load_statements() and load_record() are where that gets undone: id, document_id and
document_date are put back on each Statement so nothing downstream of this module (llm_client,
schemas, the frontend) has to know the files are grouped. A citation built from either file
therefore points at a document and a paraphrased claim, not at a line range or a verbatim quote.
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

# What separates a document id from a statement's position in it: "<document id>#<position>".
# The document id is a path and never contains one.
ID_SEPARATOR = "#"


class Actor(BaseModel):
    name: str
    organization: str


class Statement(BaseModel):
    id: str
    document_id: str
    claim: str
    actor: Actor
    speech_act: SpeechAct
    statement_date: datetime
    document_date: date
    # Worked out by the reconciliation pass from the relations, never from dates. The default
    # keeps a statements-file record loadable, and "current" is what an unlabelled statement is.
    status: Status = "current"


class _StatementBody(BaseModel):
    """A statement exactly as extraction.py writes it under its document: no id and no
    document-level fields, since every statement in the array shares its enclosing
    document's id and date."""

    claim: str
    actor: Actor
    speech_act: SpeechAct
    statement_date: datetime


class _DocumentBlock(BaseModel):
    id: str
    type: str
    date: date
    people: list[str] = []
    summary: str = ""
    statements: list[_StatementBody]


class StatementsFile(BaseModel):
    documents: list[_DocumentBlock]


class _ReconciledStatement(_StatementBody):
    """A statement in the reconciled file. It has to carry its id — the relations, problems
    and summaries point at it, and it is not laid out by document, so position cannot give it
    back — and the status the second pass worked out."""

    id: str
    status: Status


class _DocumentHead(BaseModel):
    """A document in the reconciled file: the same envelope as the statements file's, less
    the statements, which are nested under their topics there."""

    id: str
    type: str = ""
    date: date
    people: list[str] = []
    summary: str = ""


class Relation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # `from` is a keyword, so the field is `source` and the file's `from` is its alias.
    source: str = Field(alias="from")
    to: str
    kind: RelationKind


class Summary(BaseModel):
    text: str
    statements: list[str]


class _TopicBody(BaseModel):
    topic: str
    summary: Summary | None = None
    relations: list[Relation] = []
    statements: list[_ReconciledStatement]


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
    documents: list[_DocumentHead]
    topics: list[_TopicBody]
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
    """Load the reconciled file once per process, flatten it and index it.

    document_id is the statement id up to its separator and document_date comes from the
    document's entry, so neither is written on each statement. A statement whose document the
    file does not list is a broken file, and fails here rather than answering with a citation
    that has no date.

    Cached by path: the file is treated as static for the lifetime of the process, same as
    D2 assumes for what goes into the model's context. Deletion, when built, must call
    cache_clear() on this and on load_statements, or a deleted name keeps answering out of a
    warm process.
    """
    parsed = ReconciledFile.model_validate(json.loads(Path(path).read_text()))
    dates = {document.id: document.date for document in parsed.documents}
    topics = [
        Topic(
            topic=body.topic,
            summary=body.summary,
            relations=body.relations,
            statements=[_restore(statement, dates) for statement in body.statements],
        )
        for body in parsed.topics
    ]
    statements = {s.id: s for topic in topics for s in topic.statements}
    return Record(topics, parsed.problems, statements, _receipts(topics))


def _restore(statement: _ReconciledStatement, dates: dict[str, date]) -> Statement:
    document_id = statement.id.rpartition(ID_SEPARATOR)[0]
    if document_id not in dates:
        raise ValueError(f"{statement.id} names a document the file does not list")
    return Statement(
        id=statement.id,
        document_id=document_id,
        document_date=dates[document_id],
        claim=statement.claim,
        actor=statement.actor,
        speech_act=statement.speech_act,
        statement_date=statement.statement_date,
        status=statement.status,
    )


@lru_cache
def load_statements(path: str) -> dict[str, Statement]:
    """Load the statements file once per process, flatten it to one Statement per line and
    index by statement id.

    id is derived from the statement's position in its document's array —
    "<document id>#<position>", 1-indexed — the same scheme extraction.py uses internally
    to link agreements, just never written to the file since it is reconstructible for free.

    Cached by path: the file is treated as static for the lifetime of the process, same as
    D2 assumes for what goes into the model's context.
    """
    parsed = StatementsFile.model_validate(json.loads(Path(path).read_text()))
    return {
        statement.id: statement
        for document in parsed.documents
        for statement in (
            Statement(
                id=f"{document.id}{ID_SEPARATOR}{position}",
                document_id=document.id,
                document_date=document.date,
                claim=body.claim,
                actor=body.actor,
                speech_act=body.speech_act,
                statement_date=body.statement_date,
            )
            for position, body in enumerate(document.statements, start=1)
        )
    }


def load_statements_record(path: str) -> Record:
    """The statements file as a record with no currency information (ANSWER_SOURCE=statements)."""
    return Record([], [], load_statements(path), {}, reconciled=False)


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

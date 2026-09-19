"""The statements file: the one artifact the answering path reads.

Field shape follows docs/data-model.md. Not a schema until the real dataset is in hand
(decisions.md D7) — this is the interim shape the mock file and the answering path agree
on; see decisions.md D20.

The file groups statements under the document they came from — id, type, date, people and
summary live once per document, not once per statement (D36). load_statements() is where
that gets undone: id/document_id/document_date are put back on each Statement so nothing
downstream of this module (llm_client, schemas, the frontend) has to know the file is
grouped.

Per statement, only claim, actor{name, organization}, speech_act and statement_date are
carried — no location, no verbatim span, no agreed_by, no role (D37, which supersedes the
part of D36 that kept those). A citation built from this file therefore points at a
document and a paraphrased claim, not at a real line range or a verbatim quote.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

SpeechAct = Literal["proposal", "agreement", "decision", "report", "question", "objection"]


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


def load_statements(path: str) -> dict[str, Statement]:
    """Read the statements file, flatten it to one Statement per line and index by
    statement id.

    id is derived from the statement's position in its document's array —
    "<document id>#<position>", 1-indexed — the same scheme extraction.py uses internally
    to link agreements, just never written to the file since it is reconstructible for free.

    Read on every request, never cached: a cached copy is a second place a deleted person
    survives, and deletion rewrites the file (D44). A rewrite is whole-or-nothing, so a request
    sees the file from before it or after it, never half of each.
    """
    parsed = StatementsFile.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
    return {
        statement.id: statement
        for document in parsed.documents
        for statement in (
            Statement(
                id=f"{document.id}#{position}",
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


def write_statements(path: str, documents: list[dict]) -> None:
    """Replace the statements file with `documents`, whole or not at all.

    Deletion is the only thing in this service that writes the file (D46). The write goes to a
    temporary file and is renamed over the old one, so a request that arrives mid-deletion reads
    the file from before it or after it, never half of each — the guarantee load_statements()
    above relies on. The same whole-or-nothing write extraction uses when it first creates the
    file; the two are deliberately not shared, since a helper spanning both packages would be one
    more thing to trace at 2am.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(
        json.dumps({"documents": documents}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, target)

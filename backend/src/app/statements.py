"""The statements file: the one artifact the answering path reads.

Field shape follows docs/data-model.md. Not a schema until the real dataset is in hand
(decisions.md D7) — this is the interim shape the mock file and the answering path agree
on; see decisions.md D10.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

SpeechAct = Literal["proposal", "agreement", "decision", "report", "question", "objection"]


class Location(BaseModel):
    page: int | None = None
    line_start: int
    line_end: int


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


class StatementsFile(BaseModel):
    statements: list[Statement]


@lru_cache
def load_statements(path: str) -> dict[str, Statement]:
    """Load the statements file once per process and index it by statement id.

    Cached by path: the file is treated as static for the lifetime of the process, same as
    D2 assumes for what goes into the model's context.
    """
    parsed = StatementsFile.model_validate(json.loads(Path(path).read_text()))
    return {statement.id: statement for statement in parsed.statements}

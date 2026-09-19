"""Request/response shapes for the answering API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .statements import Actor, Location, SpeechAct


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    stream: bool = False


class Citation(BaseModel):
    """A citation the backend has verified against the trusted statements file.

    Every field here is copied from our own loaded copy of the statement, never from the
    model's output — see llm_client._resolve_citations. That is what lets us guarantee no
    invented citations regardless of what the model does with its input.
    """

    marker: int
    statement_id: str
    document_id: str
    location: Location
    verbatim_span: str
    actor: Actor
    agreed_by: list[Actor]
    speech_act: SpeechAct
    statement_date: datetime
    document_date: date


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]

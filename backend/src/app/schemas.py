"""Request/response shapes for the answering API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .statements import Actor, SpeechAct, Status


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    stream: bool = False


class Citation(BaseModel):
    """A citation the backend has verified against the trusted reconciled file.

    Every field here is copied from our own loaded copy of the statement, never from the
    model's output — see llm_client._resolve_citations. That is what lets us guarantee no
    invented citations regardless of what the model does with its input. The status and the
    ids that justify it are no exception: the answering model never asserts a statement's
    currency, it reads it (D40).

    There is no location or verbatim_span: neither file carries them (D37), so this points a
    judge at a document and a paraphrased claim, not at a real line range or a verbatim quote.
    """

    marker: int
    statement_id: str
    document_id: str
    claim: str
    actor: Actor
    speech_act: SpeechAct
    statement_date: datetime
    document_date: date
    # None when the answer came from the statements file: nothing was reconciled, so there is
    # no status to show, and "current" would be a claim nobody made.
    status: Status | None = None
    status_receipts: list[str] = []


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]

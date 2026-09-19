"""Request/response shapes for the answering API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .statements import Actor, SpeechAct


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    stream: bool = False


class Citation(BaseModel):
    """A citation the backend has verified against the trusted statements file.

    Every field here is copied from our own loaded copy of the statement, never from the
    model's output — see llm_client._resolve_citations. That is what lets us guarantee no
    invented citations regardless of what the model does with its input.

    There is no location or verbatim_span: the statements file does not carry them (D37),
    so this points a judge at a document and a paraphrased claim, not at a real line range
    or a verbatim quote.
    """

    marker: int
    statement_id: str
    document_id: str
    claim: str
    actor: Actor
    speech_act: SpeechAct
    statement_date: datetime
    document_date: date


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]


class DeleteRequest(BaseModel):
    name: str = Field(min_length=1)


class DeletedPerson(BaseModel):
    """Who was removed, and what the file says in their place."""

    name: str
    spellings: list[str]
    placeholder: str
    statements_changed: int
    replacements: int


class ConsideredPerson(BaseModel):
    """Someone the request could have meant. `outcome` is "removed" or "left"."""

    name: str
    statements: int
    outcome: str


class DeleteResponse(BaseModel):
    """The receipt deletion.delete_person returns, typed.

    `deleted` is null when nobody matched and the file was left alone. It is not stored
    anywhere: it names the person, and keeping it would undo the deletion (D42).
    """

    requested: str
    deleted: DeletedPerson | None
    considered: list[ConsideredPerson]
    left_in_place: list[str]

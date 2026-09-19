"""Pydantic models for the LLM's structured-output annotation pass.

The LLM is only ever asked to fill these fields -- everything else in a
segment (speaker, date, position, line numbers) comes from the deterministic
parser and is never re-derived by the model.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

SpeechAct = Literal[
    "statement",
    "proposal",
    "agreement",
    "decision",
    "report_of_decision",
    "question",
    "action_item",
    "other",
]


class SegmentAnnotation(BaseModel):
    segment_id: str
    speech_act: SpeechAct
    topics: list[str] = Field(default_factory=list)
    people_mentioned: list[str] = Field(
        default_factory=list,
        description="Names of people referenced in the text who are not the speaker/author.",
    )
    is_truncated: bool = Field(
        default=False,
        description="True if the segment cuts off mid-sentence/mid-number in the source.",
    )
    supersedes_segment_id: Optional[str] = Field(
        default=None,
        description="Set only if this segment explicitly updates/corrects an earlier "
        "segment_id given in the same batch.",
    )


class AnnotationBatch(BaseModel):
    annotations: list[SegmentAnnotation]

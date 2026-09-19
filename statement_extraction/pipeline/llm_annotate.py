"""LLM semantic-annotation pass.

Takes the deterministic segment skeleton for one document and asks the model
to fill in only the fields that actually require judgement: speech act,
topics, people mentioned in free text, whether a segment is truncated, and
whether it explicitly supersedes an earlier segment in the same document.

Segments are sent in batches (not all 100+ transcript turns in one call) and
a running topic vocabulary is threaded through the whole run so the model
reuses tags ("master-data-remediation") instead of inventing near-duplicates
per file ("master data fix").
"""
from __future__ import annotations

from typing import Any

from openai import OpenAI

from .schema import AnnotationBatch

BATCH_SIZE = 40

SYSTEM_PROMPT = """You annotate one document at a time from a meeting/email archive \
for a RAG system that must cite provenance, attribute claims to the right \
person, and track when facts changed over time.

For each segment given, decide:
- speech_act: is the speaker making a plain statement, proposing something \
(not yet agreed), agreeing/committing to something, announcing a decision, \
merely reporting a decision made elsewhere/earlier, asking a question, or \
stating an action item someone owns?
- topics: short kebab-case tags for what this segment is substantively about, \
reusing an existing tag from the provided vocabulary whenever it fits instead \
of inventing a near-duplicate.
- people_mentioned: names of people referenced in the text (not the speaker).
- is_truncated: true only if the segment's text cuts off mid-sentence or \
mid-number in a way that suggests information was lost (never true just \
because the segment is short).
- supersedes_segment_id: set only if this segment explicitly corrects or \
updates a specific earlier segment_id you were also given in this batch; \
otherwise leave null. Never guess a link that is not explicit in the text.

Do not invent facts. Do not fill in a number or word that the source did not \
actually say. If a sentence is cut off, do not complete it."""


def _segment_prompt_view(seg: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment_id": seg["segment_id"],
        "speaker_or_author": seg["speaker_or_author"],
        "text": seg["text"],
    }


def annotate_document(
    client: OpenAI,
    model: str,
    doc_meta: dict[str, Any],
    segments: list[dict[str, Any]],
    topic_vocabulary: set[str],
) -> dict[str, dict[str, Any]]:
    """Returns {segment_id: annotation_dict} for every segment across all batches."""
    results: dict[str, dict[str, Any]] = {}

    for i in range(0, len(segments), BATCH_SIZE):
        batch = segments[i : i + BATCH_SIZE]
        user_payload = {
            "doc_id": doc_meta["doc_id"],
            "doc_type": doc_meta["doc_type"],
            "doc_date": doc_meta.get("doc_date"),
            "known_topic_vocabulary": sorted(topic_vocabulary),
            "segments": [_segment_prompt_view(s) for s in batch],
        }

        completion = client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": str(user_payload)},
            ],
            response_format=AnnotationBatch,
        )
        parsed: AnnotationBatch = completion.choices[0].message.parsed

        for ann in parsed.annotations:
            results[ann.segment_id] = ann.model_dump()
            topic_vocabulary.update(ann.topics)

    return results

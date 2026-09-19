NOT_STATED = "Not stated"

# D40's escape hatch. The topic summaries and the model's problem notes are the only model-written
# prose in reconciled.json, and prose is what deletion cannot redact by matching a name. If
# deletion is not built against this file in time, set this to False: the artifact then carries
# ids and enums only. Do not ship a half-redacted summary instead.
KEEP_PROSE = True


def to_statement(record: dict) -> dict:
    """The record as the answering backend loads it (see backend/src/app/statements.py and
    docs/decisions.md D29). Extra fields ride along; the backend ignores what it does not
    declare."""
    first, last = record["lines"]
    return {
        "id": record["id"],
        "document_id": record["doc_id"],
        "doc_type": record["doc_type"],
        # D14: the genre-specific pointer (utterance offset / thread message) lives inside
        # location, next to the line range, because both are "where in it" — not a sibling
        # field a citation consumer could miss.
        "location": {
            "page": None,
            "line_start": first,
            "line_end": last,
            "position": record["position"],
        },
        "verbatim_span": record["span"],
        "claim": record["claim"],
        "speech_act": record["act"],
        "handling": record["handling"],
        "actor": _actor(record["actor"]),
        "agreed_by": [
            {**_actor(agreed), "statement": agreed["statement"]} for agreed in record["agreed_by"]
        ],
        "statement_date": record["stated_on"],
        "document_date": record["doc_date"],
    }


def _actor(actor: dict) -> dict:
    # The backend needs a string for each. A speaker the file does not name is shown by the label
    # the file uses; what no document states is "Not stated", never a guess.
    return {
        "name": actor["name"] or actor["label"] or "Unknown speaker",
        "label": actor["label"],
        "organization": actor["org"] or NOT_STATED,
        "role": actor["role"] or NOT_STATED,
    }


def to_reconciled(topics: list[dict], problems: list[dict], generated_on: str) -> dict:
    """The reconciled file: each topic with its statements nested inside, so the backend joins
    nothing (D40). A statement is to_statement plus its status, and lives in exactly one topic;
    a relation lives on its topic, once. The counts are taken from what is nested here, not from
    what went in, so they cannot disagree with the file."""
    nested = [
        {
            "topic": topic["topic"],
            "summary": topic["summary"] if KEEP_PROSE else None,
            "relations": topic["relations"],
            "statements": [
                to_statement(record) | {"status": topic["statuses"][record["id"]]}
                for record in topic["statements"]
            ],
        }
        for topic in topics
    ]
    return {
        "generated_on": generated_on,
        "statement_count": sum(len(topic["statements"]) for topic in nested),
        "topic_count": len(nested),
        "relation_count": sum(len(topic["relations"]) for topic in nested),
        "problem_count": len(problems),
        "topics": nested,
        "problems": [
            {**problem, "note": problem["note"] if KEEP_PROSE else ""} for problem in problems
        ],
    }

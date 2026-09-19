NOT_STATED = "Not stated"


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

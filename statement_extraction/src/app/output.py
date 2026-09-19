NOT_STATED = "Not stated"


def to_statement(record: dict) -> dict:
    """The record as the answering backend loads it (D31). Extra fields ride along."""
    first, last = record["lines"]
    return {
        "id": record["id"],
        "document_id": record["doc_id"],
        "doc_type": record["doc_type"],
        "location": {"page": None, "line_start": first, "line_end": last},
        "position": record["position"],
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

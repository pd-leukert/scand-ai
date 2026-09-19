NOT_STATED = "Not stated"

# D42's escape hatch. The topic summaries and the model's problem notes are the only model-written
# prose in reconciled.json, and prose is what deletion cannot redact by matching a name. If
# deletion is not built against this file in time, set this to False: the artifact then carries
# ids and enums only. Do not ship a half-redacted summary instead.
KEEP_PROSE = True


def to_statement(record: dict) -> dict:
    """One statement, nested under its document in the statements file (see extract.py's
    document envelope and backend/src/app/statements.py, which reconstructs id/document_id/
    document_date from the array position and the enclosing document — docs/decisions.md
    D36). Only what varies statement to statement lives here; what is true of every
    statement in a document — its id, type, date, people, summary — is carried once, on the
    document, not repeated on each one.

    Extra fields ride along; the backend ignores what it does not declare."""
    first, last = record["lines"]
    return {
        # D14: the genre-specific pointer (utterance offset / thread message) lives inside
        # location, next to the line range, because both are "where in it" — not a sibling
        "claim": record["claim"],
        "speech_act": record["act"],
        "actor": _actor(record["actor"]),
        "statement_date": record["stated_on"],
    }


def _actor(actor: dict) -> dict:
    # The backend needs a string for each. A speaker the file does not name is shown by the
    # label the file uses; what no document states is "Not stated", never a guess. The raw
    # label itself is dropped here — it is already folded into name and nothing downstream
    # reads it separately.
    return {
        "name": actor["name"] or actor["label"] or "Unknown speaker",
        "organization": actor["org"] or NOT_STATED,
    }


def to_reconciled(
    topics: list[dict], problems: list[dict], generated_on: str, documents: list[dict]
) -> dict:
    """The reconciled file: each topic with its statements nested inside, so the backend joins
    nothing (D42). A statement lives in exactly one topic; a relation lives on its topic, once.
    The counts are taken from what is nested here, not from what went in, so they cannot
    disagree with the file.

    Reduced the way the statements file is (D36, D37), for the same reason and by the same
    means (D46). What is true of every statement in a document — its type, date, people,
    summary — is written once, in `documents`, and the backend puts document_id and
    document_date back from the id and that table. Per statement only claim, actor, speech_act
    and statement_date are kept, as in the statements file, plus the two things only this file
    has: the status, and the id — which the statements file leaves out because its position in
    a document gives it back, and which this file cannot, because the relations, problems and
    summaries point at it and the statements here are laid out by topic, not by document."""
    known = {document["id"] for document in documents}
    nested = [
        {
            "topic": topic["topic"],
            "summary": topic["summary"] if KEEP_PROSE else None,
            "relations": topic["relations"],
            "statements": [
                {"id": record["id"]}
                | to_statement(record)
                | {"status": topic["statuses"][record["id"]]}
                for record in topic["statements"]
            ],
        }
        for topic in topics
    ]
    # The backend takes a statement's document from its id and its date from this table, so a
    # statement whose document is missing is a citation with no date. Stop here, not there.
    stray = {
        record["doc_id"]
        for topic in topics
        for record in topic["statements"]
        if record["doc_id"] not in known
    }
    if stray:
        raise ValueError(f"statements from documents the file does not list: {sorted(stray)}")
    return {
        "generated_on": generated_on,
        "statement_count": sum(len(topic["statements"]) for topic in nested),
        "topic_count": len(nested),
        "relation_count": sum(len(topic["relations"]) for topic in nested),
        "problem_count": len(problems),
        "documents": documents,
        "topics": nested,
        "problems": [
            {**problem, "note": problem["note"] if KEEP_PROSE else ""} for problem in problems
        ],
    }

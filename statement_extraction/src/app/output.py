NOT_STATED = "Not stated"


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

"""Run the extraction job: read the corpus, ask the model, write the statements file.

EXTRACTION_MODEL=<model> uv run python -m src.app.extract [DOC_ID_SUBSTRING ...]
"""

import json
import os
import sys
from pathlib import Path

import httpx

from .documents import load_corpus
from .extraction import SCHEMA, Chat, extract_document, link_agreements
from .output import to_statement


def _ollama_chat(client: httpx.Client, model: str, num_ctx: int) -> Chat:
    def chat(messages: list[dict[str, str]], schema: dict = SCHEMA) -> dict:
        response = client.post(
            "/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                # Copying is not a reasoning task, and a thinking model can spend its whole
                # budget thinking and return nothing.
                "think": False,
                "format": schema,
                "options": {"temperature": 0, "num_ctx": num_ctx},
            },
        )
        response.raise_for_status()
        return json.loads(response.json()["message"]["content"])

    return chat


def main(filters: list[str]) -> int:
    model = os.environ.get("EXTRACTION_MODEL")
    if not model:
        print(
            "EXTRACTION_MODEL is not set: name the Ollama model to extract with.", file=sys.stderr
        )
        return 2
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if "://" not in host:
        host = f"http://{host}"
    num_ctx = int(os.environ.get("EXTRACTION_NUM_CTX", "8192"))
    batch_words = int(os.environ.get("EXTRACTION_BATCH_WORDS", "300"))
    timeout = float(os.environ.get("EXTRACTION_TIMEOUT", "600"))
    corpus = Path(os.environ.get("CORPUS_DIR", Path(__file__).parents[3] / "input"))
    out = Path(os.environ.get("STATEMENTS_PATH", "statements.json"))

    docs = load_corpus(corpus)
    total = len(docs)
    if filters:
        docs = [doc for doc in docs if any(part in doc.doc_id for part in filters)]
    if not docs:
        print(f"No document in {corpus} matches {filters}.", file=sys.stderr)
        return 2

    records: list[dict] = []
    empty: list[str] = []
    with httpx.Client(base_url=host, timeout=timeout) as client:
        chat = _ollama_chat(client, model, num_ctx)
        for doc in docs:
            found, dropped = extract_document(doc, chat, batch_words)
            linked = link_agreements(found, chat)
            records.extend(found)
            if not found:
                empty.append(doc.doc_id)
            note = f", dropped {dict(dropped)}" if dropped else ""
            print(
                f"{doc.doc_id}: {len(found)} statements{note}, responses {dict(linked)}", flush=True
            )

    # Nothing extracted must not look like a finished record: exit non-zero so compose holds
    # the backend, and leave any earlier file alone.
    if not records:
        print("No statements were extracted, so nothing was written.", file=sys.stderr)
        return 1

    # Written whole or not at all: a half-written file must never look like the record.
    tmp = out.with_name(out.name + ".tmp")
    statements = [to_statement(record) for record in records]
    tmp.write_text(
        json.dumps({"statements": statements}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, out)
    partial = f" (only {len(docs)} of {total} documents)" if len(docs) < total else ""
    print(f"Wrote {len(records)} statements to {out}{partial}")
    if empty:
        # A document with no statements is a silent gap in the record, so the job fails.
        print(f"No statements from: {', '.join(empty)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

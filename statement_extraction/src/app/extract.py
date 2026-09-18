"""Run the extraction job: read the corpus, ask the model, write the statements file.

EXTRACTION_MODEL=<model> uv run python -m src.app.extract [DOC_ID_SUBSTRING ...]
"""

import json
import os
import sys
from pathlib import Path

import httpx

from .documents import load_corpus
from .extraction import SCHEMA, Chat, extract_document


def _ollama_chat(client: httpx.Client, model: str, num_ctx: int) -> Chat:
    def chat(messages: list[dict[str, str]]) -> dict:
        response = client.post(
            "/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                # Copying is not a reasoning task, and a thinking model can spend its whole
                # budget thinking and return nothing.
                "think": False,
                "format": SCHEMA,
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
    batch_words = int(os.environ.get("EXTRACTION_BATCH_WORDS", "1000"))
    timeout = float(os.environ.get("EXTRACTION_TIMEOUT", "600"))
    corpus = Path(os.environ.get("CORPUS_DIR", Path(__file__).parents[3] / "corpus"))
    out = Path(os.environ.get("STATEMENTS_PATH", "statements.jsonl"))

    docs = load_corpus(corpus)
    total = len(docs)
    if filters:
        docs = [doc for doc in docs if any(part in doc.doc_id for part in filters)]
    if not docs:
        print(f"No document in {corpus} matches {filters}.", file=sys.stderr)
        return 2

    records: list[dict] = []
    with httpx.Client(base_url=host, timeout=timeout) as client:
        chat = _ollama_chat(client, model, num_ctx)
        for doc in docs:
            found, dropped = extract_document(doc, chat, batch_words)
            records.extend(found)
            note = f", dropped {dict(dropped)}" if dropped else ""
            print(f"{doc.doc_id}: {len(found)} statements{note}", flush=True)

    # Written whole or not at all: a half-written file must never look like the record.
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    os.replace(tmp, out)
    partial = f" (only {len(docs)} of {total} documents)" if len(docs) < total else ""
    print(f"Wrote {len(records)} statements to {out}{partial}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Run the extraction job: read the corpus, ask the model, write the statements file.

EXTRACTION_LLM_MODEL=<model> uv run python -m src.app.extract [DOC_ID_SUBSTRING ...]
"""

import json
import os
import shutil
import sys
from pathlib import Path

import httpx

from .documents import Document, load_corpus
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


def _write_json(path: Path, documents: list[dict]) -> None:
    """Written whole or not at all: a half-written file must never look like the record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps({"documents": documents}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _document_block(doc: Document, found: list[dict]) -> dict:
    """One document's envelope: what is true of every statement in it, carried once, plus
    its statements. Backend/src/app/statements.py puts document_id/document_date back on
    each statement when it loads this (docs/decisions.md D36) — nothing downstream of that
    function has to know the file is grouped."""
    return {
        "id": doc.doc_id,
        "type": doc.doc_type,
        "date": doc.doc_date,
        "people": list(doc.attendees),
        "summary": doc.summary,
        "statements": [to_statement(record) for record in found],
    }


def main(filters: list[str]) -> int:
    model = os.environ.get("EXTRACTION_LLM_MODEL")
    if not model:
        print(
            "EXTRACTION_LLM_MODEL is not set: name the Ollama model to extract with.",
            file=sys.stderr,
        )
        return 2
    # EXTRACTION_LLM_BASE_URL is the OpenAI-compatible URL the rest of compose.yaml uses
    # (D23); this job calls Ollama's native /api/chat instead, for schema-constrained
    # output (D28), so the "/v1" the answering path needs is stripped back off here.
    host = os.environ.get("EXTRACTION_LLM_BASE_URL", "http://localhost:11434").removesuffix("/v1")
    num_ctx = int(os.environ.get("EXTRACTION_NUM_CTX", "32768"))
    timeout = float(os.environ.get("EXTRACTION_TIMEOUT", "600"))
    corpus = Path(os.environ.get("CORPUS_DIR", Path(__file__).parents[3] / "input"))
    out = Path(os.environ.get("STATEMENTS_FILE_PATH", "statements.json"))
    # One JSON file per document, written as soon as that document is done, so progress is
    # visible while a slow model works through the corpus and a crash partway through does
    # not lose the documents already finished. The final file below is just these
    # concatenated, per doc_id, never assembled any other way.
    per_doc_dir = out.parent / "documents"

    docs = load_corpus(corpus)
    total = len(docs)
    if filters:
        docs = [doc for doc in docs if any(part in doc.doc_id for part in filters)]
    if not docs:
        print(f"No document in {corpus} matches {filters}.", file=sys.stderr)
        return 2

    empty: list[str] = []
    with httpx.Client(base_url=host, timeout=timeout) as client:
        chat = _ollama_chat(client, model, num_ctx)
        for doc in docs:
            try:
                found, dropped = extract_document(doc, chat)
                linked = link_agreements(found, chat)
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                # A truncated or malformed model response must not take the whole corpus
                # down with it — the documents already written (this loop, D35) and the
                # ones still to come are both worth more than crashing here. Treated the
                # same as a document that legitimately produced nothing: recorded in
                # `empty`, so the job still fails loudly overall.
                print(f"{doc.doc_id}: extraction call failed ({exc})", file=sys.stderr)
                found, dropped, linked = [], {}, {}
            if not found:
                empty.append(doc.doc_id)
            note = f", dropped {dict(dropped)}" if dropped else ""
            print(
                f"{doc.doc_id}: {len(found)} statements{note}, responses {dict(linked)}", flush=True
            )
            doc_out = per_doc_dir / f"{doc.doc_id}.json"
            _write_json(doc_out, [_document_block(doc, found)])
            print(f"  wrote {doc_out}", flush=True)

    # The massive file is exactly these, concatenated in the same order docs were walked in.
    merged: list[dict] = []
    for doc in docs:
        doc_out = per_doc_dir / f"{doc.doc_id}.json"
        merged.extend(json.loads(doc_out.read_text(encoding="utf-8"))["documents"])
    total_statements = sum(len(document["statements"]) for document in merged)

    # Nothing extracted must not look like a finished record: exit non-zero so compose holds
    # the backend, and leave any earlier file alone.
    if not total_statements:
        print("No statements were extracted, so nothing was written.", file=sys.stderr)
        return 1

    _write_json(out, merged)
    # per_doc_dir was scratch: visible progress and crash resilience while the run was in
    # flight, nothing once the merge it exists for has succeeded. Kept around it would be a
    # second copy of every actor name and verbatim span outside the one derived artifact
    # deletion knows how to reach (CLAUDE.md rule 4) — an interrupted run still leaves it
    # behind, which is the point, but a clean run does not.
    shutil.rmtree(per_doc_dir, ignore_errors=True)
    partial = f" (only {len(docs)} of {total} documents)" if len(docs) < total else ""
    print(f"Wrote {total_statements} statements across {len(merged)} documents to {out}{partial}")
    if empty:
        # A document with no statements is a silent gap in the record, so the job fails.
        print(f"No statements from: {', '.join(empty)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

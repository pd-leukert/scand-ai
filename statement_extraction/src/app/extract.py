"""Run the extraction job: read the corpus, ask the model, write the statements file, then
reconcile the statements by topic and write the reconciled file (D42).

EXTRACTION_LLM_MODEL=<model> uv run python -m src.app.extract [DOC_ID_SUBSTRING ...]
"""

import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path

import httpx

from .documents import Document, load_corpus
from .extraction import SCHEMA, Chat, extract_document, link_agreements
from .output import to_reconciled, to_statement
from .reconcile import ReconcileError, reconcile


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


def _document_head(doc: Document) -> dict:
    """What is true of every statement in a document, carried once. Both files use it: the
    statements file puts the statements inside it, and the reconciled file keeps it as a table
    and nests the statements under their topics instead (D46)."""
    return {
        "id": doc.doc_id,
        "type": doc.doc_type,
        "date": doc.doc_date,
        "people": list(doc.attendees),
        "summary": doc.summary,
    }


def _document_block(doc: Document, found: list[dict]) -> dict:
    """One document's envelope: its head, plus its statements. Backend/src/app/statements.py
    puts document_id/document_date back on each statement when it loads this (docs/decisions.md
    D36) — nothing downstream of that function has to know the file is grouped."""
    return {**_document_head(doc), "statements": [to_statement(record) for record in found]}


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
    # Reconciliation is a second pass with its own model, defaulting to the first pass's (D42).
    reconcile_model = os.environ.get("RECONCILE_LLM_MODEL") or model
    reconcile_num_ctx = int(os.environ.get("RECONCILE_NUM_CTX", "8192"))
    reconcile_batch = int(os.environ.get("RECONCILE_BATCH_STATEMENTS", "20"))
    reconcile_timeout = float(os.environ.get("RECONCILE_TIMEOUT", "600"))
    topic_cap = int(os.environ.get("RECONCILE_TOPIC_MAX", "40"))
    vocabulary_shown = int(os.environ.get("RECONCILE_VOCABULARY_SHOWN", "40"))
    max_untagged = float(os.environ.get("RECONCILE_MAX_UNTAGGED", "0.1"))
    max_topics = float(os.environ.get("RECONCILE_MAX_TOPICS", "0.35"))
    max_topic_share = float(os.environ.get("RECONCILE_MAX_TOPIC_SHARE", "0.5"))
    max_flagged = float(os.environ.get("RECONCILE_MAX_FLAGGED", "0.5"))
    reconciled_out = Path(os.environ.get("RECONCILED_FILE_PATH", "reconciled.json"))
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

    # What reconciliation reads. The per-document files below hold the written shape
    # (to_statement), which has dropped the fields the second pass needs, so the raw records
    # are kept here alongside them (D42).
    records: list[dict] = []
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
            records.extend(found)
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
    print(
        f"Wrote {total_statements} statements across {len(merged)} documents to {out}{partial} "
        f"— {_file_size(out)}"
    )
    if empty:
        # A document with no statements is a silent gap in the record, so the job fails.
        print(f"No statements from: {', '.join(empty)}", file=sys.stderr)
        return 1

    # Only a complete record is reconciled, and a failure here is a failed run: compose then
    # holds the backend rather than let it answer from a half-reconciled record, and any
    # earlier reconciled file is left alone.
    try:
        with httpx.Client(base_url=host, timeout=reconcile_timeout) as client:
            chat = _ollama_chat(client, reconcile_model, reconcile_num_ctx)
            topics, problems, discarded = reconcile(
                records,
                chat,
                batch=reconcile_batch,
                vocabulary_shown=vocabulary_shown,
                topic_cap=topic_cap,
                max_untagged=max_untagged,
                max_topics=max_topics,
                max_topic_share=max_topic_share,
                max_flagged=max_flagged,
                progress=lambda line: print(line, flush=True),
            )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ReconcileError) as error:
        print(
            f"Reconciliation failed, so {reconciled_out} was not written: {error!r}",
            file=sys.stderr,
        )
        return 1

    tmp = reconciled_out.with_name(reconciled_out.name + ".tmp")
    reconciled = to_reconciled(
        topics, problems, date.today().isoformat(), [_document_head(doc) for doc in docs]
    )
    tmp.write_text(json.dumps(reconciled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, reconciled_out)
    print(f"Dropped in reconciliation: {dict(discarded)}" if discarded else "Nothing dropped.")
    print(
        f"Wrote {reconciled['statement_count']} statements in {reconciled['topic_count']} topics, "
        f"{reconciled['relation_count']} relations and {reconciled['problem_count']} problems "
        f"to {reconciled_out} — {_file_size(reconciled_out)}"
    )
    for problem in problems:
        print(f"  [{problem['kind']}] {problem['topic']}: {', '.join(problem['statements'])}")
        print(f"    {problem['note']}")
    print(_size_report(out, reconciled_out))
    return 0


def _file_size(path: Path) -> str:
    """How large a finished output file is, for the line that announces it."""
    size = path.stat().st_size
    return f"{size / 1000:,.1f} kB ({size:,} bytes)"


# Bytes of reconciled.json per token of answering prompt. The file is not what is sent: the
# backend drops fields it does not declare and re-serialises without the indentation, so this
# folds the shrink and the tokenizer into one number. Measured end to end on qwen3:0.6b — a
# 114 kB reconciled file became a 29,356-token prompt, or 3.9 bytes a token. Rounded down, so
# the figure printed errs high: this number is read by whoever is choosing
# OLLAMA_CONTEXT_LENGTH, and guessing that low is the failure D45 exists to stop.
RECONCILED_BYTES_PER_TOKEN = 3.5


def _size_report(statements_path: Path, reconciled_path: Path) -> str:
    """D2's ceiling is unmeasured until something measures it. The whole reconciled file goes
    into the answering context as plain JSON (D45), so report what that actually costs — this
    line is what OLLAMA_CONTEXT_LENGTH and LLM_NUM_CTX have to be set above.

    Rough on purpose: another model's tokenizer will differ, and the estimate deliberately errs
    high. It is the order of magnitude that decides whether D2 holds, and Ollama truncates a
    prompt over its context silently."""
    before, after = statements_path.stat().st_size, reconciled_path.stat().st_size
    tokens = round(after / RECONCILED_BYTES_PER_TOKEN)
    return (
        f"{statements_path.name} {before // 1000} kB, {reconciled_path.name} {after // 1000} kB "
        f"({(after - before) / before:+.0%}), about {tokens // 1000}k tokens in the answering "
        f"context — set OLLAMA_CONTEXT_LENGTH and LLM_NUM_CTX above {tokens // 1000}k, or the "
        "backend will refuse every question (D45)."
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

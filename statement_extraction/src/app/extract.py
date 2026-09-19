"""Run the extraction job: read the corpus, ask the model, write the statements file, then
reconcile the statements by topic and write the reconciled file (D31).

EXTRACTION_LLM_MODEL=<model> uv run python -m src.app.extract [DOC_ID_SUBSTRING ...]
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

import httpx

from .documents import load_corpus
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
    num_ctx = int(os.environ.get("EXTRACTION_NUM_CTX", "8192"))
    batch_words = int(os.environ.get("EXTRACTION_BATCH_WORDS", "300"))
    timeout = float(os.environ.get("EXTRACTION_TIMEOUT", "600"))
    corpus = Path(os.environ.get("CORPUS_DIR", Path(__file__).parents[3] / "input"))
    out = Path(os.environ.get("STATEMENTS_FILE_PATH", "statements.json"))
    # Reconciliation is a second pass with its own model, defaulting to the first pass's (D31).
    reconcile_model = os.environ.get("RECONCILE_LLM_MODEL") or model
    reconcile_num_ctx = int(os.environ.get("RECONCILE_NUM_CTX", "8192"))
    reconcile_batch = int(os.environ.get("RECONCILE_BATCH_STATEMENTS", "20"))
    reconcile_timeout = float(os.environ.get("RECONCILE_TIMEOUT", "600"))
    topic_cap = int(os.environ.get("RECONCILE_TOPIC_MAX", "40"))
    vocabulary_shown = int(os.environ.get("RECONCILE_VOCABULARY_SHOWN", "40"))
    max_untagged = float(os.environ.get("RECONCILE_MAX_UNTAGGED", "0.1"))
    max_topics = float(os.environ.get("RECONCILE_MAX_TOPICS", "0.35"))
    reconciled_out = Path(os.environ.get("RECONCILED_FILE_PATH", "reconciled.json"))

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
                progress=lambda line: print(line, flush=True),
            )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ReconcileError) as error:
        print(
            f"Reconciliation failed, so {reconciled_out} was not written: {error!r}",
            file=sys.stderr,
        )
        return 1

    tmp = reconciled_out.with_name(reconciled_out.name + ".tmp")
    reconciled = to_reconciled(topics, problems, date.today().isoformat())
    tmp.write_text(json.dumps(reconciled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, reconciled_out)
    print(f"Dropped in reconciliation: {dict(discarded)}" if discarded else "Nothing dropped.")
    print(
        f"Wrote {reconciled['statement_count']} statements in {reconciled['topic_count']} topics, "
        f"{reconciled['relation_count']} relations and {reconciled['problem_count']} problems "
        f"to {reconciled_out}"
    )
    for problem in problems:
        print(f"  [{problem['kind']}] {problem['topic']}: {', '.join(problem['statements'])}")
        print(f"    {problem['note']}")
    print(_size_report(out, reconciled_out))
    return 0


# Base64 tokenises badly. Measured on qwen3:0.6b: a 95 kB reconciled file became a 56k-token
# prompt, about 2.3 characters a token, where prose is about 4.
BASE64_CHARS_PER_TOKEN = 2.3


def _size_report(statements_path: Path, reconciled_path: Path) -> str:
    """D2's ceiling is unmeasured until something measures it. The whole reconciled file goes
    into the answering context, base64-encoded (D21), so report what that actually costs.

    Rough on purpose: the file's bytes include indentation and fields the backend never sends,
    and another model's tokenizer will differ. It is the order of magnitude that decides whether
    D2 holds, and Ollama truncates a prompt over its context silently."""
    before, after = statements_path.stat().st_size, reconciled_path.stat().st_size
    tokens = round(after * 4 / 3 / BASE64_CHARS_PER_TOKEN)
    return (
        f"{statements_path.name} {before // 1000} kB, {reconciled_path.name} {after // 1000} kB "
        f"({(after - before) / before:+.0%}), about {tokens // 1000}k tokens once base64-encoded "
        "into the answering context."
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

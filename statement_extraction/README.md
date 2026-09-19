# Statement extraction

Offline job that turns the source documents into two files, in two passes. It runs once.

1. **Extraction.** Walks `input/` one document at a time, asks the model for that document's
   statements, and writes the statements file.
2. **Reconciliation** (D40). Strictly after the first pass has finished. Stage A tags every
   statement with a topic, in batches, showing each batch the topics already in use so the
   vocabulary converges. Stage B makes one call per topic, and the model writes the relations
   it can see between that topic's statements: `supersedes`, `corrects`, `conflicts-with`,
   `answers`. Code then derives each statement's status — `current`, `stale`, `never-true`,
   `disputed` or `unresolved` — from the relations that survive validation, never from dates,
   and writes the reconciled file: the statements nested inside their topics, with the
   relations, a one-sentence summary per topic, and a list of problems.

The model is shown statements under local labels (`S1`, `S2`, …), never their ids, and
anything it returns that does not name a real statement is dropped and counted. Nothing in
`reconcile.py` writes a new quote.

It is a script, not a server: it exits 0 on success, non-zero if anything went wrong, and
compose holds the backend and frontend until it has (D12). **A failure in either pass is a
failed run.** If reconciliation fails, or a hard gate trips, nothing is written for that
pass and any earlier reconciled file is left alone. Exit codes: 0 done, 1 a failed run
(including a document that yielded no statements, which stops the job before reconciliation),
2 not configured.

At the end of a run it prints what was dropped, one line per topic, every problem it found,
and the size of both files with a token estimate for the answering context. That last line is
D2's ceiling, measured.

Before changing it, read [docs/corpus.md](../docs/corpus.md) — what the 45 documents
actually look like, and the traps planted in them — and
[docs/data-model.md](../docs/data-model.md) — what every statement has to carry. Location
semantics are fixed by [D14](../docs/decisions.md).

Run locally with `EXTRACTION_LLM_MODEL=<model> uv run python -m src.app.extract` from the
`statement_extraction` folder. Pass one or more substrings as arguments to extract only
matching documents (by `doc_id`), e.g. `... extract 07_2024-11-12`.

In a container: `docker compose up statement-extraction` from the repo root. It waits on
the `ollama-pull` job, so the model is on disk before this runs, and the backend and
frontend wait on it in turn.

Each document gets its own JSON file under `documents/`, next to `STATEMENTS_FILE_PATH`
(e.g. `documents/transcripts/07_2024-11-12_....json`), written as soon as that document is
done — the run logs its path, so progress is visible while a slow model works through the
corpus. `STATEMENTS_FILE_PATH` itself is these files concatenated, in doc-id order. This
directory is scratch, not a second output: a successful run deletes it once the merge is
written, so there is exactly one place a deleted person has to be removed from (CLAUDE.md
rule 4). It only survives a run that never reached that point — an interrupted job, or one
where every document came back empty — which is also when it's most useful for figuring out
what happened.

## Configuration

- `EXTRACTION_LLM_MODEL` — required. The Ollama model to extract with.
- `EXTRACTION_LLM_BASE_URL` — the `ollama` service, `http://ollama:11434/v1` in compose.
  This job calls Ollama's native `/api/chat` for schema-constrained output, not the
  OpenAI-compatible path the backend uses, so the trailing `/v1` is stripped before use.
- `CORPUS_DIR` — defaults to `input/`, baked into the image at build time (D18).
- `STATEMENTS_FILE_PATH` — where the result is written, `/data/statements.json` in compose.
  Same variable name the backend reads: one name for the one artifact.
- `EXTRACTION_NUM_CTX` — the context window passed to Ollama. Defaults to 32768; a whole
  document goes in one model call (D31), and a context too small to hold the document plus
  its statements truncates the model's JSON mid-object and crashes the job (D36a) — raise
  this further before assuming a document is the problem.
- `EXTRACTION_TIMEOUT` — per-request timeout in seconds. Defaults to 600.
- `RECONCILED_FILE_PATH` — where the reconciled file is written, `/data/reconciled.json` in
  compose, next to the statements file. The backend reads it under the same variable name.
- `RECONCILE_LLM_MODEL` — the model for the second pass. Defaults to `EXTRACTION_LLM_MODEL`,
  which compose defaults to `LLM_MODEL`. Reconciliation is a reasoning pass over short
  contexts, not a copying task, so it may want a different one. `ollama-pull` pulls it too.
- `RECONCILE_NUM_CTX` (8192), `RECONCILE_TIMEOUT` (600) — as their `EXTRACTION_` twins.
- `RECONCILE_BATCH_STATEMENTS` — statements per topic-tagging call. Defaults to 20.
- `RECONCILE_VOCABULARY_SHOWN` — how many of the most-used topics each tagging batch is
  shown. Defaults to 40.
- `RECONCILE_TOPIC_MAX` — statements in one reconciliation call. A larger topic is cut into
  near-equal consecutive chunks, and a link across the cut is not seen. Defaults to 40.
- `RECONCILE_MAX_UNTAGGED` — the share of statements that may come back untagged before the
  run fails. Defaults to 0.1.
- `RECONCILE_MAX_TOPICS` — topics per statement above which the run fails. Defaults to 0.35.
  These two gates exist for the failure that looks like success: a grouping so fragmented
  that no topic holds two statements, so no link is found and the whole record comes out
  `current` with exit 0. **The thresholds are guesses until the first run on the real
  corpus**, and a run over one or two documents can trip the topic gate legitimately — set
  `RECONCILE_MAX_TOPICS=1` for a smoke run.
- `RECONCILE_MAX_TOPIC_SHARE` — the share of all statements one topic may hold before the run
  fails. Defaults to 0.5. The same failure from the other end: everything in one bucket finds
  no real links either, because each reconciliation call is then shown unrelated statements.
  A small run legitimately has one big topic — set it to 1 for a smoke run. See D42.
- `RECONCILE_MAX_FLAGGED` — per topic, the share of statements a relation may put in
  `never-true`, `stale` or `disputed` before the run fails. Defaults to 0.5. A model that
  links each statement to the next one in the list flags nearly everything, and `corrects` is
  not date-guarded, so nothing else rejects it. `unresolved` does not count towards this: it
  comes from a proposal nobody answered, not from a link. See D42.

These are deliberately separate from the backend's `LLM_BASE_URL`/`LLM_MODEL`: extraction
and answering are allowed to use different models, and the working agreement says never to
assume otherwise. See [decision D23](../docs/decisions.md).

## Tests

`uv run --frozen pytest` from this folder. Most tests are pure parsing/matching logic and
need nothing running; a few skip unless `input/` (or `CORPUS_DIR`) points at the real
archive, which it does by default when run from a checkout.
Compose passes `EXTRACTION_LLM_BASE_URL` (the `ollama` service) and `EXTRACTION_LLM_MODEL`
(default `qwen3:0.6b`, the laptop model — the VM overrides it, see
[D25](../docs/decisions.md)). These are deliberately separate from the backend's
`LLM_BASE_URL`/`LLM_MODEL`: extraction and answering are allowed to use different models,
and the working agreement says never to assume otherwise. See
[decision D23](../docs/decisions.md). Nothing reads them yet — the real extraction pass
does.

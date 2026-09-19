# Statement extraction

Offline job that turns the source documents into the statements file. It runs once, walks
`input/` one document at a time, asks the model for that document's statements, and writes
the result. It is a script, not a server: it exits 0 on success, non-zero if anything went
wrong, and compose holds the backend and frontend until it has (D12).

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

## Configuration

- `EXTRACTION_LLM_MODEL` — required. The Ollama model to extract with.
- `EXTRACTION_LLM_BASE_URL` — the `ollama` service, `http://ollama:11434/v1` in compose.
  This job calls Ollama's native `/api/chat` for schema-constrained output, not the
  OpenAI-compatible path the backend uses, so the trailing `/v1` is stripped before use.
- `CORPUS_DIR` — defaults to `input/`, baked into the image at build time (D18).
- `STATEMENTS_FILE_PATH` — where the result is written, `/data/statements.json` in compose.
  Same variable name the backend reads: one name for the one artifact.
- `EXTRACTION_BATCH_WORDS` — how many words of a document go in one model call. Defaults
  to 300; raise it on a machine with a bigger context budget.
- `EXTRACTION_NUM_CTX` — the context window passed to Ollama. Defaults to 8192.
- `EXTRACTION_TIMEOUT` — per-request timeout in seconds. Defaults to 600.

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

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
  its statements truncates the model's JSON mid-object and crashes the job (D36) — raise
  this further before assuming a document is the problem.
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

## Deleting a person

`uv run python -m src.app.delete "Kwame Boateng"` rewrites the statements file in place, replacing
that person with a role placeholder everywhere they appear, and prints a receipt. `--dry-run` shows
the receipt and changes nothing. There is no backup: it would be a second copy of the name. Run it
in compose with `docker compose run --rm --no-deps statement-extraction uv run --frozen python -m
src.app.delete "<name>"`. The backend reads the file on every request, so it answers from the
rewrite straight away. How it works and where it stands: [docs/deletion.md](../docs/deletion.md), [D37 and D38](../docs/decisions.md).

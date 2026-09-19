# Backend

Live web service for processing user requests. Gathers the `Statement DB` and exposes a RESTful API to the frontend.

It reads one derived file and **nothing else** — not the source documents, not extraction,
not the model's own knowledge. By default that is the reconciled file: the statements grouped
by topic, with the relations between them and a status on each (stale, never-true, disputed,
unresolved, or current), worked out by the extraction job's second pass ([D40](../docs/decisions.md)).
If the statements do not support an answer, the answer is that the record is silent. See
[CLAUDE.md](../CLAUDE.md) rule 2 and [docs/architecture.md](../docs/architecture.md).

Each citation carries the statement's `status` and `status_receipts`, the ids of the
statements that put it there. Both are copied from our own loaded file, never from the
model's output — the model reads a currency, it does not assert one.

Run with `uv run fastapi dev` from the `backend` folder.

## Configuration

`/query` calls an OpenAI-compatible chat-completions endpoint (Ollama in production, per
[decisions.md](../docs/decisions.md) D8). Required env vars:

- `LLM_BASE_URL` — API root, e.g. `http://ollama:11434/v1`. `/chat/completions` is
  appended.
- `LLM_MODEL` — model name. Never hardcode this; extraction and answering may use
  different models.

Optional:

- `LLM_API_KEY` — sent as `Authorization: Bearer ...` if set. Ollama doesn't need one.
- `LLM_NUM_CTX` — how many tokens the Ollama server is configured to serve, i.e. whatever
  `OLLAMA_CONTEXT_LENGTH` is set to on the `ollama` service. This does **not** ask for a
  context: Ollama's OpenAI-compatible endpoint ignores `options.num_ctx`, so the server is the
  only place that number can be set. It is what the backend measures its own prompt against —
  over it, `/query` returns 413 saying so instead of letting Ollama truncate the record
  silently and answer from the part it kept. Unset turns the guard off. Raise this and
  `OLLAMA_CONTEXT_LENGTH` together or it protects nothing. See D43.
- `LLM_TIMEOUT` — seconds to wait on one answer, default 120. The whole record is processed as
  prompt before the first token, so the wait scales with the record and with the box: compose
  sets 1800, which is what a record at the default `LLM_NUM_CTX` costs on a laptop CPU
  (measured at about 17 tokens a second). Over it, `/query` returns 504 naming this variable
  rather than a bare 500. Raise it whenever you raise `OLLAMA_CONTEXT_LENGTH`. See D43.
- `ANSWER_SOURCE` — which derived file to answer from: `reconciled` (the default) or
  `statements`. Read at startup, so changing it means restarting the backend. In `statements`
  mode the backend behaves as it did before D40: the model gets the flat list under the
  original prompt, which says currency is unknowable, and every citation has `status: null`
  and no receipts. It never sends `current` for statements nobody reconciled. In compose,
  `ANSWER_SOURCE=statements docker compose up` switches it; both files are on the volume.
- `RECONCILED_FILE_PATH` — the reconciled file. Defaults to the mock at
  `src/app/data/mock_reconciled.json` (the mock statements wrapped in two topics, one
  relation, one problem — its statuses are written by hand, not derived). Points at the real
  file once extraction produces one; compose sets it to `/data/reconciled.json`.
- `STATEMENTS_FILE_PATH` — the flat statements file, read only when `ANSWER_SOURCE=statements`.
  Defaults to the mock at `src/app/data/mock_statements.json`; compose sets it to
  `/data/statements.json`. This name has to match what extraction writes, or the backend
  silently falls back to the bundled mock.
- `DUMMY_LLM` — set to `true` to skip the model call entirely and answer from a canned
  response built out of the loaded record (real citations, no model, and the new `status`
  and `status_receipts` fields on the wire). Also lifts
  the `LLM_BASE_URL`/`LLM_MODEL` requirement. For exercising `/query` end to end — both
  `stream: false` and the SSE `stream: true` path — without Ollama running. See
  [decisions.md](../docs/decisions.md) D15.
- `DUMMY_LLM_DELAY_SECONDS` — seconds slept between tokens on the dummy SSE stream, so it
  reads like a real streaming answer instead of arriving all at once. Defaults to `0.05`;
  only used when `DUMMY_LLM` is set.
Run with `uv run fastapi dev` from the `backend` folder

In a container: `docker compose up backend` from the repo root. Compose sets both required
variables for you — `LLM_BASE_URL` points at the `ollama` service and `LLM_MODEL` defaults
to `qwen3:0.6b`, overridable from the environment. It runs statement extraction
and the model pull first, and starts this service only once both jobs have exited. See
[decision D23](../docs/decisions.md).

`LLM_MODEL` defaults to a small CPU model so a laptop needs no configuration; the VM sets
it to the real one ([D25](../docs/decisions.md)).

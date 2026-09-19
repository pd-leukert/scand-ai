# Backend

Live web service for processing user requests. Gathers the `Statement DB` and exposes a RESTful API to the frontend.

It reads the statements file and **nothing else** — not the source documents, not
extraction, not the model's own knowledge. If the statements do not support an answer, the
answer is that the record is silent. See [CLAUDE.md](../CLAUDE.md) rule 2 and
[docs/architecture.md](../docs/architecture.md).

Run with `uv run fastapi dev` from the `backend` folder.

The file is read on every request and never cached, so a deletion (which rewrites it) shows up
in the next answer with no restart ([D39](../docs/decisions.md)).

## Configuration

`/query` calls an OpenAI-compatible chat-completions endpoint (Ollama in production, per
[decisions.md](../docs/decisions.md) D8). Required env vars:

- `LLM_BASE_URL` — API root, e.g. `http://ollama:11434/v1`. `/chat/completions` is
  appended.
- `LLM_MODEL` — model name. Never hardcode this; extraction and answering may use
  different models.

Optional:

- `LLM_API_KEY` — sent as `Authorization: Bearer ...` if set. Ollama doesn't need one.
- `LLM_TIMEOUT` — seconds of silence from the model before the answering call gives up.
  Defaults to `600`. This is a read timeout (time between chunks), not a cap on the whole
  answer, but a large model can still take minutes to produce its first token against the
  full statements payload — raise this before raising `LLM_MODEL`'s size. The frontend's
  own `BACKEND_REQUEST_TIMEOUT` (frontend/README.md) should stay at or above this value, or
  it becomes the next thing that cuts the answer off.
- `STATEMENTS_FILE_PATH` — defaults to the mock file at `src/app/data/mock_statements.json`.
  Points at the real derived statements file once extraction produces one.
- `DUMMY_LLM` — set to `true` to skip the model call entirely and answer from a canned
  response built out of the loaded statements file (real citations, no model). Also lifts
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

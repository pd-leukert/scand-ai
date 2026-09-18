# Backend

Live web service for processing user requests. Gathers the `Statement DB` and exposes a RESTful API to the frontend.

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
- `STATEMENTS_FILE_PATH` — defaults to the mock file at `src/app/data/mock_statements.json`.
  Points at the real derived statements file once extraction produces one.

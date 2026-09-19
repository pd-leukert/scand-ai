# Statement extraction

Offline service that turns the source documents into the statements file. Placeholder for
now: it starts, serves `/health`, and exits by itself one minute after startup.

Before writing the real thing, read [docs/corpus.md](../docs/corpus.md) — what the 45
documents actually look like, and the traps planted in them — and
[docs/data-model.md](../docs/data-model.md) — what every statement has to carry. Location
semantics are fixed by [D14](../docs/decisions.md); this runs once and offline, never from
the request path.

Run with `uv run fastapi dev` from the `statement_extraction` folder

In a container: `docker compose up statement-extraction` from the repo root. It is a job —
it exits, and the backend and frontend are held until it does. It waits in turn on the
`ollama-pull` job, so the model is on disk before this runs.

## Configuration

Compose passes `EXTRACTION_LLM_BASE_URL` (the `ollama` service) and `EXTRACTION_LLM_MODEL`
(default `qwen3.8:27b-mtp-bf16`). These are deliberately separate from the backend's
`LLM_BASE_URL`/`LLM_MODEL`: extraction and answering are allowed to use different models,
and the working agreement says never to assume otherwise. See
[decision D23](../docs/decisions.md). Nothing reads them yet — the real extraction pass
does.

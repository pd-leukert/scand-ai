# Backend

Live web service for processing user requests. Gathers the `Statement DB` and exposes a RESTful API to the frontend.

It reads the statements file and **nothing else** — not the source documents, not
extraction, not the model's own knowledge. If the statements do not support an answer, the
answer is that the record is silent. See [CLAUDE.md](../CLAUDE.md) rule 2 and
[docs/architecture.md](../docs/architecture.md).

Run with `uv run fastapi dev` from the `backend` folder

In a container: `docker compose up backend` from the repo root. Compose runs statement
extraction first and starts this service only once that job has exited.

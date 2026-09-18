# Statement extraction

Offline service that turns the source documents into the statements file. Placeholder for
now: it starts, serves `/health`, and exits by itself one minute after startup.

Run with `uv run fastapi dev` from the `statement_extraction` folder

In a container: `docker compose up statement-extraction` from the repo root. It is a job —
it exits, and the backend and frontend are held until it does.

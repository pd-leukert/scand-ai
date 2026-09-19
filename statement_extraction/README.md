# Statement extraction

Offline service that turns the source documents into the statements file. Placeholder for
now: it starts, serves `/health`, and exits by itself one minute after startup.

Run with `uv run fastapi dev` from the `statement_extraction` folder

Extract with `EXTRACTION_MODEL=<model> uv run python -m src.app.extract [DOC_ID_SUBSTRING ...]`.
It needs Ollama at `OLLAMA_HOST` (default `http://localhost:11434`) with that model pulled, and
writes `statements.json` (or `STATEMENTS_PATH`). Give a substring such as `07_2024` to try
one document. In compose: `docker compose -f compose.yaml -f compose.extraction.yaml up`, plus
`-f compose.gpu.yaml` on an NVIDIA machine. See docs/decisions.md D18.

Test with `uv run pytest` from the same folder. The corpus tests read `corpus/` at the repo
root, or `CORPUS_DIR`, and skip when it is absent.

In a container: `docker compose up statement-extraction` from the repo root. It is a job —
it exits, and the backend and frontend are held until it does.

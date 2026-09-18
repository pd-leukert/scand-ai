# Backend

Live web service for processing user requests. Gathers the `Statement DB` and exposes a RESTful API to the frontend.

Run with `uv run fastapi dev` from the `backend` folder

In a container: `docker compose up backend` from the repo root. Compose runs statement
extraction first and starts this service only once that job has exited.

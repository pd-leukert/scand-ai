# frontend

Streamlit. The URL we submit, and the thing the judges use themselves.

It holds no logic: its job is to make the receipt visible — every claim expandable to the
document, the location and the quoted line, in one interaction. Anything it computes is
something we would have to delete from twice. See
[docs/demo.md](../docs/demo.md) for what it has to support on Sunday.

Run with `uv run streamlit run app.py` from the `frontend` folder

In a container: `docker compose up frontend` from the repo root, then open
<http://localhost:8501>.

## Configuration

- `BACKEND_URL` — where the backend lives. Defaults to `http://localhost:8000`.
- `BACKEND_REQUEST_TIMEOUT` — seconds of silence from `/query` before giving up on it, not
  a cap on the whole answer (see `stream_backend()` in app.py). Defaults to `600`, matching
  the backend's own `LLM_TIMEOUT` default (backend/README.md) — keep the two in step, or a
  large model that the backend was configured to wait for gets cut off here instead.

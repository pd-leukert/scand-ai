# frontend

Streamlit. The URL we submit, and the thing the judges use themselves.

It holds no logic: its job is to make the receipt visible — every claim expandable to the
document, the location and the quoted line, in one interaction. Anything it computes is
something we would have to delete from twice. See
[docs/demo.md](../docs/demo.md) for what it has to support on Sunday.

Run with `uv run streamlit run app.py` from the `frontend` folder

In a container: `docker compose up frontend` from the repo root, then open
<http://localhost:8501>.

## Deleting a person

"Delete a person" in the header opens a dialog that calls the backend's `POST /delete`. The
confirmation names who was removed and who was resolved but deliberately left — the archive has
two people sharing a first name, and that sentence is the difference between a kept bystander and
a redaction that missed ([D47](../docs/decisions.md)). Nothing about it is stored: the receipt
lives in session state until the dialog closes. See [docs/deletion.md](../docs/deletion.md).

## Theme

Light only, pinned in [.streamlit/config.toml](.streamlit/config.toml) with the same tokens
`app.py` declares on `:root` ([D48](../docs/decisions.md)). Without it Streamlit's own widgets
follow the browser's dark-mode preference while our CSS stays light, and half the page goes dark.

One Streamlit quirk to know before adding a component: it sizes a markdown element's box
expecting the default `1rem` bottom margin on its last child, so a block whose last child sets
`margin:0` measures 16px short and whatever follows lands on top of it. `STYLE` gives that margin
back for every block; keep the rule when editing the stylesheet.

## Configuration

- `BACKEND_URL` — where the backend lives. Defaults to `http://localhost:8000`.
- `BACKEND_REQUEST_TIMEOUT` — seconds of silence from `/query` before giving up on it, not
  a cap on the whole answer (see `stream_backend()` in app.py). Defaults to `600`, matching
  the backend's own `LLM_TIMEOUT` default (backend/README.md) — keep the two in step, or a
  large model that the backend was configured to wait for gets cut off here instead.

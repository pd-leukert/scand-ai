# Statement extraction

Offline job that turns the source documents into per-document JSON: parse (deterministic)
-> annotate (LLM) -> merge -> write, one file per document under `--out-dir`, plus a
`_topic_vocabulary.json` threaded across the whole run. It is not yet the single merged
statements file the backend's `Statement` contract expects (docs/decisions.md has the
open item) — that reconciliation is a separate change.

Runs once: if `--out-dir` already has extracted documents in it (from a previous
`docker compose up`, since `/data` is the named `statements` volume and survives a
container being recreated), `pipeline.run` prints why and exits 0 without calling the
model. Pass `--force` to re-run anyway.

Before touching this, read [docs/corpus.md](../docs/corpus.md) — what the 45 documents
actually look like, and the traps planted in them — and
[docs/data-model.md](../docs/data-model.md) — what every statement has to carry. Location
semantics are fixed by [D14](../docs/decisions.md); this runs once and offline, never from
the request path.

Run locally with `uv run python -m pipeline.run --dry-run` from the `statement_extraction`
folder (`--dry-run` skips the LLM call and fills semantic fields with defaults, so you can
check the deterministic parser on its own first). Drop `--dry-run` once `EXTRACTION_LLM_*`
below is set, or pass `--files`/`--model`/`--base-url` directly — see `pipeline/run.py`'s
module docstring.

In a container: `docker compose up statement-extraction` from the repo root. It is a job —
it exits, and the backend and frontend are held until it does. It waits in turn on the
`ollama-pull` job, so the model is on disk before this runs, and reads `../input/` (the
corpus, baked into the image per D18) for its default file list.

## Configuration

Compose passes `EXTRACTION_LLM_BASE_URL` (the `ollama` service) and `EXTRACTION_LLM_MODEL`
(default `qwen3.8:27b-mtp-bf16`) to `pipeline.run`'s `--base-url`/`--model` defaults.
These are deliberately separate from the backend's `LLM_BASE_URL`/`LLM_MODEL`: extraction
and answering are allowed to use different models, and the working agreement says never to
assume otherwise. See [decision D23](../docs/decisions.md). `EXTRACTION_LLM_API_KEY` is
optional — the OpenAI SDK requires some key be set even though Ollama's OpenAI-compatible
endpoint ignores it, so this defaults to a dummy value when unset.

# scand-ai — Memory With a Receipt

Team **scand-ai** · RELEX Solutions challenge track · AaltoAI Hackathon 2026

## The problem in one paragraph

Two years into a rollout, nobody agrees on what was decided. There are 45 documents —
transcripts, email threads, status reports — and the people who were in the room have
changed jobs. Ask a normal AI assistant to "summarise what was agreed" and you get a
clean, confident, wrong answer: a reversed decision reported as current, a consultant's
suggestion reported as a customer agreement, a record that was never true repeated as
fact.

We are building an agent that answers the same questions and can **show its receipts**.

## What the agent has to do

| # | Requirement | Our position |
|---|---|---|
| 1 | **Cite everything** — document, and where in it | In scope for the MVP. Every claim carries document, location, and the verbatim span it came from. No citation means we treat it as a guess. |
| 2 | **Suggestion ≠ commitment** | In scope. Extraction records what kind of speech act a statement is, who made it, and for whom they spoke. |
| 3 | **Know stale from wrong** | Out of scope for the MVP, planned next. See [roadmap](docs/roadmap.md). |
| 4 | **Delete a person** | In scope, with a deliberate and documented interpretation. See [decision D3](docs/decisions.md). |
| 5 | **Do one thing unasked** | Proposed: flag statements meant to be private. See [D19](docs/decisions.md) and [roadmap](docs/roadmap.md). |

Scoring weights and how the judges test it: [docs/challenge.md](docs/challenge.md).

## How it works

Three long-running containers and one job that runs once.

1. **The pile.** The customer's PDFs and text files sit in plain object/file storage on
   Verda. We never edit them.
2. **Statement extraction (job).** Walks the documents one at a time, puts each through a
   local LLM, and pulls out every statement it contains — who said it, when, what kind of
   claim it was, and exactly where in the document it appears. The results from all
   documents are aggregated into a single statements file. This runs once, offline.
3. **Backend.** A Python/FastAPI service that takes a user question, puts the statements
   file in the model's context, and answers from it — with citations.
4. **Frontend.** A Streamlit app the judges open in a browser and use themselves.

Full picture, including what each boundary is for: [docs/architecture.md](docs/architecture.md).

## Repository map

```
docs/
  challenge.md      the brief and the rubric, as we read it
  architecture.md   containers, dataflow, deployment
  data-model.md     what a statement records, and why (conceptual)
  decisions.md      the decision log — read before proposing changes
  roadmap.md        MVP boundary, planned extensions, honest limits
  demo.md           judging prep: what we show, in what order
  extraction.md     how extraction works and how to run it, locally and on Verda
  whats-left.md     what is done, what is blocked, what is unowned — updated in place
CLAUDE.md           working agreement for humans and coding agents
```

## Working in this repo

Python everywhere, `uv` for dependencies and running things, one container per service.
Read [CLAUDE.md](CLAUDE.md) before your first commit — it is short, and the rules in it
are the ones that protect our score.

## Running the whole thing

```bash
docker compose up --build
```

Statement extraction runs first; the backend and the frontend do not start until it has
finished and exited. The UI is then on <http://localhost:8501>. The backend is not
published — it is reachable from inside the compose network only, which is what
[architecture.md](docs/architecture.md) asks for.

That runs the placeholder extraction job. Real extraction, with Ollama, is a separate compose
layer: see [docs/extraction.md](docs/extraction.md) and [decision D18](docs/decisions.md).

## Status

In progress. The documents are in hand. Extraction is built and tested, but has only run on
one transcript: the full run needs a GPU on Verda, and the backend that answers from the
statements file, deletion, and the receipts in the UI are not built. See
[docs/extraction.md](docs/extraction.md). The other documents describe the intent so that
everyone — and every agent — builds the same thing.

# scand-ai — Memory With a Receipt

Team **scand-ai** · RELEX Solutions challenge track · AaltoAI Hackathon 2026

## The problem in one paragraph

A year into a rollout, nobody agrees on what was decided. There are 45 documents —
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
| 5 | **Do one thing unasked** | Not yet chosen. Placeholder in [roadmap](docs/roadmap.md). |

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
CLAUDE.md           working agreement for humans and coding agents
```

## Working in this repo

Python everywhere, `uv` for dependencies and running things, one container per service.
Read [CLAUDE.md](CLAUDE.md) before your first commit — it is short, and the rules in it
are the ones that protect our score.

## Status

Pre-implementation. The documents are not in hand yet and nothing is built. These
documents describe the intent so that everyone — and every agent — builds the same thing.

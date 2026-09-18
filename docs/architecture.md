# Architecture

MVP shape. Deliberately small: four moving parts, one of which only runs once.
Technical detail (schemas, endpoints, file layouts) is intentionally absent until the
dataset is in hand — see [decisions.md](decisions.md), D7.

## The shape

```
   Verda file storage
   ┌──────────────────┐
   │  45 source docs  │   PDFs and text files, read-only, never modified
   └────────┬─────────┘
            │  read once
            ▼
   ┌──────────────────────────────┐        ┌──────────────┐
   │  statement_extraction (job)  │───────▶│    Ollama    │
   │  one document at a time      │◀───────│  local LLM   │
   └────────┬─────────────────────┘        └──────┬───────┘
            │  writes once                        │
            ▼                                     │
   ┌──────────────────┐                           │
   │  statements file │  the derived artifact      │
   └────────┬─────────┘                           │
            │  loaded into context                │
            ▼                                     │
   ┌──────────────────┐   REST    ┌───────────────┴──┐
   │   Streamlit UI   │◀─────────▶│  backend (API)   │
   └──────────────────┘           └──────────────────┘
            ▲
            │  HTTPS
      the judges
```

## The parts

### 1. The pile — source documents

Plain file storage on Verda. Read-only from the application's point of view: nothing in
the running system writes to it. Keeping the corpus immutable is what lets us say
precisely what our derived artifact was derived from.

### 2. statement_extraction — the one-shot job

A Python/FastAPI service in its own container, but conceptually a batch job: it runs once,
before the demo, and its output is a file.

It walks the documents one at a time. Each document goes to a local LLM, which returns the
statements that document contains — every assertion, proposal, agreement, decision or
report, with who made it, when, in what capacity, and exactly where in the document it
sits. The per-document results are aggregated into a single statements file.

Why per-document and not corpus-wide: one document fits in a context window, 45 do not,
and a single document is a unit we can re-run in isolation when extraction of it is wrong.
The cost of this choice is that no single extraction call can see that a later document
reversed an earlier decision — which is exactly why currency is out of MVP scope and needs
a second pass over the aggregated table. See [roadmap.md](roadmap.md).

It is a FastAPI service rather than a script so that re-extraction of a single document,
and later the deletion operation, can be triggered without redeploying anything.

### 3. backend — the customer-facing API

Python/FastAPI, its own container. Takes a user question over REST, puts the statements
file in the model's context, asks the local LLM to answer *from the statements only*, and
returns the answer together with its citations.

The rule this service exists to enforce: **the model answers from the statements file, not
from its own knowledge.** A claim that cannot point at a statement, and through it at a
document and a location, does not go in the answer.

### 4. frontend — Streamlit

The URL we submit. Its job is to make the receipt visible: an answer is not a paragraph,
it is a paragraph whose claims can be expanded into the document, the location, and the
quoted line they came from. The judges check citations by hand, so the shortest path from
a claim to its source passage is a scoring decision, not a UI nicety.

## Deployment

One Verda VM, `docker compose`, three long-running containers (frontend, backend, Ollama)
plus the extraction job run on demand. Streamlit exposed publicly over HTTPS; the backend
and Ollama are not reachable from outside the compose network.

Verda is the cloud for everything in this project — storage, compute, and the model host.
No external model APIs: inference is local Ollama throughout.

The model is a configuration value, not an architectural commitment. Extraction and
answering may end up on different models; nothing outside the configuration should assume
otherwise.

## Boundaries, and why they are where they are

- **Extraction is offline and the backend is online.** Answering never invokes extraction.
  If a question needs something extraction did not capture, the answer is "not in the
  record", not an improvised read of the source document.
- **The statements file is the only thing the backend reads.** Not the PDFs. This is what
  makes deletion meaningful: there is exactly one derived artifact, so "gone from
  everything we derived" is a claim we can actually verify.
- **The frontend holds no logic.** Anything it computes is something we would have to
  delete from twice.

## What the MVP does not have

No retrieval layer, no embeddings, no vector store, no cross-document reconciliation, no
cached summaries. Each of those is a second place a deleted person could survive, and the
MVP is small partly so that deletion stays provable. When they arrive, deletion has to
cascade to them — that is a condition of adding them, not a follow-up task.

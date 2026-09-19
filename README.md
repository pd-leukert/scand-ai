# scand-ai — Memory With a Receipt

Team **scand-ai** · RELEX Solutions challenge track · AaltoAI Hackathon 2026

## The problem in one paragraph

Two years into a software rollout, nobody agrees on what was decided. There are 45
documents — 23 Teams transcripts, 20 email threads, 2 status-report threads — and the
people who were in the room have changed jobs. Ask a normal AI assistant to "summarise
what was agreed" and you get a clean, confident, wrong answer: a reversed decision
reported as current, a consultant's suggestion reported as a customer agreement, a record
that was never true repeated as fact.

We are building an agent that answers the same questions and can **show its receipts**.

The archive is invented — Acme Org is a fictional EMEA grocery retailer, and no RELEX
customer data is involved. RELEX is named throughout it and the record is unflattering
about how the vendor handled things. That is deliberate: the right answer is what the
record says, not the polite version.

## What the agent has to do

| # | Requirement | Our position |
|---|---|---|
| 1 | **Cite everything** — document, and where in it | In scope for the MVP. Every claim carries document, location, and the verbatim span it came from. No citation means we treat it as a guess. |
| 2 | **Suggestion ≠ commitment** | In scope. Extraction records what kind of speech act a statement is, who made it, and for whom they spoke. |
| 3 | **Know stale from wrong** | In scope. A second LLM pass groups the statements by topic, writes explicit supersedes / corrects / contradicts links between them, and derives a status for each from those links — never from dates. See [D40](docs/decisions.md), which supersedes D4 and D16. |
| 4 | **Delete a person** | In scope, with a deliberate and documented interpretation. See [D3](docs/decisions.md) and [D19](docs/decisions.md). |
| 5 | **Do one thing unasked** | Not yet chosen — [Q1](docs/open-questions.md). Candidates and evidence in [roadmap](docs/roadmap.md). |
| — | **Residency** — the archive stays in the EU | In scope and structural: Verda, local Ollama, no external model APIs. See [architecture](docs/architecture.md#residency). |

Scoring weights, how the judges test it, and what we have to hand in on Sunday:
[docs/challenge.md](docs/challenge.md).

## How it works

Three long-running containers and one job that runs once.

1. **The pile.** 45 plain-text documents, read-only. We never edit them. What is in them,
   and the traps they contain: [docs/corpus.md](docs/corpus.md).
2. **Statement extraction (job).** Walks the documents one at a time, puts each through a
   local LLM, and pulls out every statement it contains — who said it, when, what kind of
   claim it was, and exactly where in the document it appears. The results from all
   documents are aggregated into a single statements file. Then a second pass over those
   statements groups them by topic, writes down which supersede, correct, contradict or
   answer which, and derives a status for each (current, stale, never-true, disputed,
   unresolved) from those links alone. That is written to a second file, the reconciled
   file. This all runs once, offline, and both files stay on the shared volume.
3. **Backend.** A Python/FastAPI service that takes a user question, puts the reconciled
   file in the model's context, and answers from it — with citations that carry each
   statement's status and the statements that justify it. `ANSWER_SOURCE=statements`
   switches it to the flat statements file, with no currency information at all.
4. **Frontend.** A Streamlit app the judges open in a browser and use themselves.

Full picture, including what each boundary is for: [docs/architecture.md](docs/architecture.md).

## Repository map

```
input/              the archive: 45 source documents, read-only
docs/
  challenge.md      the brief and the rubric, as we read it
  corpus.md         what is actually in input/ — formats, cast, planted traps
  archive-readme.md the handout's own manifest, verbatim
  practice-questions.md  the nine practice questions, verbatim — answers are a deliverable
  architecture.md   containers, dataflow, deployment, residency
  data-model.md     what a statement records, and why (conceptual)
  decisions.md      the decision log — read before proposing changes
  open-questions.md what we have deliberately not decided yet
  roadmap.md        MVP boundary, planned extensions, honest limits
  demo.md           judging prep: what we submit and what we show, in what order
CLAUDE.md           working agreement for humans and coding agents
```

New here — human or agent? Read [CLAUDE.md](CLAUDE.md), then
[docs/challenge.md](docs/challenge.md), then [docs/corpus.md](docs/corpus.md). The rest is
reference.

## Working in this repo

Python everywhere, `uv` for dependencies and running things, one container per service.
Read [CLAUDE.md](CLAUDE.md) before your first commit — it is short, and the rules in it
are the ones that protect our score.

## Running the whole thing

```bash
docker compose up --build
```

On a laptop that is all of it: no flags, no `.env`, CPU only, and a small model
(`qwen3:0.6b`, ~520 MB) pulled automatically. Enough to prove the wiring end to end, and
nothing at all about answer quality.

The VM is the same command plus four environment variables, set once in Coolify:

```
OLLAMA_RUNTIME=nvidia                    # stock runtime ignores the GPU without this
OLLAMA_DATA_DIR=/root/ollama-data        # bind the weights already on disk
LLM_MODEL=qwen3.8:27b-mtp-bf16           # also drives extraction unless overridden
OLLAMA_CONTEXT_LENGTH=131072             # the whole record goes in one prompt (D2)
```

Set none of them and you get the laptop stack; set **all four** and you get the real one.
They are independent, so a partial set runs in a half-state rather than failing — a 27B
model on CPU will crawl, not error, and a missing `OLLAMA_DATA_DIR` silently re-downloads
tens of gigabytes it already has. The `ollama-pull` job prints the configuration it
resolved and warns on all of those, so check the top of its deploy log
([D26](docs/decisions.md), [D43](docs/decisions.md)).

**`OLLAMA_CONTEXT_LENGTH` is the one that decides whether the thing answers at all.** D2
puts the entire reconciled record in every prompt, and the full 45-document corpus is well
over 100k tokens, so the 16384 default holds a handful of documents and no more. Ollama
truncates a prompt over its context without saying so, so the backend measures its own
prompt against `LLM_NUM_CTX` (which defaults to whatever this is set to) and answers **413
with both numbers** rather than answer from the part of the record that survived. A deploy
that leaves this at the default comes up healthy and refuses every question — which is the
intended behaviour, not a bug, but it is not a demo. Set it to what the model can actually
serve, and remember the KV cache that buys: measure before the day.

`OLLAMA_RUNTIME=nvidia` needs a *named* `nvidia` runtime registered with the Docker daemon.
`docker run --gpus all` working does not prove that — `--gpus` takes a different code path.
Verify with `docker info | grep -A3 -i runtimes`, and if it is missing, run
`sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker`. See
[decision D25](docs/decisions.md).

Statement extraction runs first; the backend and the frontend do not start until it has
finished and exited. The UI is then on <http://localhost:8501>. The backend is not
published — it is reachable from inside the compose network only, which is what
[architecture.md](docs/architecture.md) asks for.

Ollama runs as a fourth container on the same VM, on the GPU only when
`OLLAMA_RUNTIME=nvidia` is set. A one-shot `ollama-pull` job downloads the model into the
model store (a named volume on a laptop, the `OLLAMA_DATA_DIR` bind on the VM) before
extraction or the backend start, so the first question can never hit a missing model; a
re-pull of a model that is already there is a no-op, so only the first run is slow. All three models are configuration —
`LLM_MODEL` for answering, `EXTRACTION_LLM_MODEL` for extraction and `RECONCILE_LLM_MODEL`
for the reconciliation pass, each defaulting to the one before it (D40). See [decision D23](docs/decisions.md) for the Ollama service and
[D25](docs/decisions.md) for the laptop/VM switch.

## Status

**The archive is in hand** (`input/`, since Friday). Nothing is built yet: the three
services are skeletons and no code reads a document or calls a model. These documents
describe the intent so that everyone — and every agent — builds the same thing.

Still open, and tracked in [docs/open-questions.md](docs/open-questions.md): the
initiative feature, who answers the nine practice questions, and which EU region the
Verda VM is in. Everything else that was open on Friday is now decided — see
[D14](docs/decisions.md) through [D19](docs/decisions.md).

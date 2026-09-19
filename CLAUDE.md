# Working agreement — scand-ai

For everyone working in this repo, human or coding agent. Short on purpose. Read
[docs/decisions.md](docs/decisions.md) before proposing anything that contradicts it.

## What we are building

An agent that answers questions about **two years** of rollout documents — 45 plain-text
transcripts, email threads and status reports about a fictional customer — and can show
its receipts. Read [README.md](README.md) and [docs/challenge.md](docs/challenge.md)
first — most design questions are already answered there, and the rubric is what decides
ties. Before touching anything that reads a document, read
[docs/corpus.md](docs/corpus.md): the archive is deliberately messy and the traps in it
are specific.

## Rules that protect the score

These are not style preferences. Breaking one of them costs us a scoring slice.

1. **Never invent a citation.** Every claim the system emits points at a real document, a
   real location in it, and a verbatim span that actually appears there. If code cannot
   guarantee that, it must emit no citation rather than an approximate one. Prompts say
   this too, explicitly.
2. **The answering path reads the statements file and nothing else.** It does not read
   source documents, does not call extraction, and does not fall back on the model's own
   knowledge. If the statements do not support an answer, the answer is that the record is
   silent.
3. **Deletion changes the derived artifact.** Never implement deletion as a filter applied
   at query time, or as a prompt instruction telling the model to avoid a name. The judges
   test precisely this. And redaction includes the verbatim spans, not just the actor
   fields — the span is the one place we are guaranteed to show a judge. **A person is not
   a string:** the archive holds one person spelled two ways and two people sharing a
   first name, so deletion resolves an identity first and its receipt says which person it
   resolved to (D19).
4. **Do not add a second derived artifact without making deletion cascade to it.** Caches,
   embeddings, indexes, pre-computed summaries: each is a new place a deleted person
   survives. Adding one and wiring deletion into it is a single piece of work, not two.
5. **Do not fake a currency signal.** We do not classify statements as stale or
   never-true in the MVP (D4). Do not add a date heuristic that looks like one.
6. **Extraction stays offline.** It runs once, deliberately. Nothing in the request path
   invokes an LLM over a source document.

## Tooling

- **Python everywhere. `uv` for dependencies and for running things** — `uv sync`,
  `uv run`, `uv add`. Not pip, not poetry, not a hand-rolled venv. Lockfiles are committed.
- One container per service, `docker compose` on a single Verda VM.
- **Verda is the cloud for everything.** No external model APIs — inference is local
  Ollama, always. This is the EU-residency requirement, which is scored: the archive and
  every prompt derived from it stay on an EU host. One convenient call to a non-EU API
  costs the sovereignty marks outright.
- The model is a configuration value. Never hardcode a model name outside configuration,
  and never assume extraction and answering use the same one.

## Code

- Match the surrounding code. Comment density, naming and structure should look like what
  is already there rather than like a different project.
- Hackathon pace is fine. Cleverness that needs explaining is not — on Sunday morning
  somebody else has to change this code under time pressure.
- Prefer the boring version. Every abstraction is something to debug at 2am.
- Keep the three services' boundaries intact even when crossing them would be quicker. The
  frontend holds no logic; anything it computes is something we would have to delete from
  twice.

## The decision log is not optional

**If you make a call that was not already written down, add an entry to
[docs/decisions.md](docs/decisions.md) in the same change.** This applies to coding agents
as much as to people, and it applies to decisions made while implementing something, not
just to decisions made in meetings.

The test: did you weigh two options? Then it is an entry. Say what you chose, what you
rejected, why, and what it costs us. Append; never rewrite history — if a decision is
reversed, add a new entry superseding the old one.

A change that quietly contradicts an existing decision is worse than one that argues
against it. Argue in a new entry.

## Definition of done, for anything user-facing

- A judge who has never seen it can use it without being told how.
- Every claim it emits can be expanded to its source in one interaction.
- It fails honestly: "the record does not say" and "the record conflicts" are good answers
  and should be reachable, not edge cases.

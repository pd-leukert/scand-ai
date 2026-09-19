# Open questions

Things we have deliberately **not** decided, so that nobody mistakes an open question for
a settled one and builds against a guess. Decisions live in
[decisions.md](decisions.md); this is the list of holes in it.

When one of these is answered, write the entry in `decisions.md` and delete it from here.
Unlike the decision log, this file *is* meant to be rewritten.

---

## Q1 — What does the agent do unasked? (15% of the rubric)

**Status:** not yet agreed, 2026-09-19. **Needed by:** it has to be working in the
deployed version, so realistically Saturday evening.

The brief offers four directions and says the archive supports all four. The shortlist,
the evidence for each, and what each one costs are in [roadmap.md](roadmap.md) — in short:

| Option | Cost | Catch |
|---|---|---|
| Audience-scoped answering (INTERNAL / PARTNER / customer) | Low — the markers are already in the corpus | Reads as query-time filtering, which the deletion slice punishes; needs an argument for why it is legitimate here |
| Contradiction alarm when a new document arrives | High — needs the reconciliation pass (D16) | Best demo moment in the list |
| Drift report: agreed vs. actually done | High — same dependency | Practice question P8 asks almost exactly this |
| Monday-morning briefing for a joiner | Lowest | Closest to "a search engine with footnotes", which the brief names as the thing to beat |

Whoever decides: write the entry, update [demo.md](demo.md) step 4, and say what was
rejected.

## Q2 — Who answers the nine practice questions, and when?

**Status:** not decided, 2026-09-19. **Needed by:** Sunday 12:00 — answers *with
citations* are submission deliverable 3, not optional practice.

The options weighed: run all nine through the agent once it works and verify every
citation by hand (honest, but blocked on the pipeline and lands late); answer them by hand
now in parallel as a ground-truth set to test the agent against (costs a person-day of
build time, and is not evidence the agent works); or split — hand-answer P7 and P9 now
because they shape the architecture, agent-answer the rest.

Whichever way it goes, the deadline does not move, and P9 is the one where a correct
citation and a wrong conclusion score nothing. See [corpus.md](corpus.md) for what each
question is probing.

## Q3 — Which EU region is the Verda VM in?

**Status:** unconfirmed, 2026-09-19. **Needed by:** the one-page design document.

Not a decision — a fact nobody has checked. Residency is scored, the deployment has to be
in the EU (D17), and "it is Verda" is not an answer to "where inference runs". Somebody
open the console and write the region into
[architecture.md](architecture.md#residency).

## Q5 — What stops our own tooling from undoing a deletion?

**Status:** not decided, 2026-09-19. **Needed by:** before the first deletion on the deployed VM.

A deletion rewrites `statements.json` — from the page or from the command, both in the backend
(D46) — and two things we already do can put the person back or leave them behind:

1. **`docker compose up` re-runs extraction.** D12 says so in its cost line, and `extract.py`
   writes the file unconditionally. A restart or a redeploy after a deletion brings the person back
   with no warning, on the one slice the brief tests directly. D3 states the condition ("no
   re-extraction after a deletion") but nothing enforces it.
2. **An interrupted extraction run leaves `documents/` behind.** It holds one file per document
   with every name in it, and deletion does not reach it (rule 4). A clean run removes it.

| Option | Answers | Catch |
|---|---|---|
| The extraction job skips itself when the statements file already exists; re-extracting means removing the file on purpose | 1 | Changes extraction's behaviour, which its owner has to agree to, and a first run on a fresh volume is unaffected. Cheapest to check. |
| A runbook: after a deletion, only ever restart with `docker compose up --no-deps backend` | 1 | No code, but it holds only while nobody forgets it under Sunday-morning pressure. |
| The job clears `documents/` when it starts, and on any exit | 2 | Loses the leftover files that are useful for working out why a run stopped. |
| Keep a list of who was deleted and replay it after a re-extraction | 1 | Rejected in advance: the list keeps the names, which undoes the deletion. |

**Leaning:** skip extraction when the file exists, for 1, and clear `documents/` at the start of a
run, for 2. Both are changes to extraction, so they are its owner's call.

Whoever decides: write the entry in [decisions.md](decisions.md), update
[deletion.md](deletion.md), and delete this.

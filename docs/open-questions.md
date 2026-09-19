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

## Q4 — How does a judge trigger a deletion on the deployed app?

**Status:** not decided, 2026-09-19. **Needed by:** Saturday evening. It has to work in the
deployed version, and it gates the receipt in the UI ([deletion.md](deletion.md) steps 3 and 5).

The brief says judges open the URL and use it themselves on Sunday, and that they pick the person
([challenge.md](challenge.md#how-it-is-tested)). A command we run in a terminal is therefore not
enough: the page has to be able to call it, and a judge who has never seen the page has to be able
to use it (CLAUDE.md, definition of done). The deletion itself is built ([D42](decisions.md),
[D43](decisions.md)); what is missing is a way for the page to reach it.

What any answer has to respect: the frontend holds no logic and has no volume; the backend mounts
the file read-only and D12 gives the file one writer; the deletion code lives in
`statement_extraction` and should exist once; and whatever takes the request must not be published
beyond the compose network, with the frontend calling it from the server side.

| Option | What it takes | Catch |
|---|---|---|
| A. A small server built from the extraction image, as a fourth compose service | Same image and code, the shared volume read-write, one endpoint that runs `delete_person` and returns the receipt. The frontend gets a "delete a person" control that shows it. `fastapi` goes back into `statement_extraction`'s dependencies. | A fourth service is a boundary change and needs its own decision. Extraction stopped being a server when D12 made it a job, so the reason [architecture.md](architecture.md) gives for it being FastAPI is out of date. |
| B. The backend gets a write path | Mount the volume read-write into the backend and add `POST /delete`. | Breaks D12's one writer and the backend's "reads the statements file and nothing else". The deletion code has to be copied into the backend or shared between two packages, so there are two copies to keep the same. |
| C. We run the command by hand when a judge names someone | Nothing new: `docker compose run --rm --no-deps statement-extraction uv run --frozen python -m src.app.delete "<name>"`. | Judges use the app themselves, so this fails the definition of done. It is a fallback for a demo we run, not a plan for the graded URL. |

**Leaning:** A. It is the only option that keeps the code in one place and the file at one writer.
The cost of being wrong is a fourth service to build and deploy on Saturday evening. If that slips,
C is the fallback, and we would say so on Saturday, the way the brief asks us to about hosting.

Two things to settle whichever option wins. Anyone who opens the page can delete anybody,
permanently, on the instance the next judge will use: a judge who deletes Kwame Boateng early
leaves the next judge without him for provenance questions such as P1. A reset needs either a
re-extraction (slow, and see Q5) or a copy of the file, which is a second copy of every name
(rule 4). And the receipt names the person, so the page shows it and stores nothing.

Whoever decides: write the entry in [decisions.md](decisions.md), update
[deletion.md](deletion.md) steps 3 and 5, and delete this.

## Q5 — What stops our own tooling from undoing a deletion?

**Status:** not decided, 2026-09-19. **Needed by:** before the first deletion on the deployed VM.

A deletion rewrites `statements.json`, and two things we already do can put the person back or
leave them behind:

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

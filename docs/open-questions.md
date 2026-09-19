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

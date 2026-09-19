# Demo and judging prep

Submissions close **Sunday 20 September, 12:00**. Grading runs until 13:00 — the judges
open our URL and use it themselves — and pitches follow: **five minutes of demo, five
minutes of questions.**

## What we hand in — all five, not just the URL

| # | Deliverable | Where it comes from | Status |
|---|---|---|---|
| 1 | A deployed agent, with a URL | the Streamlit frontend, on the Verda VM, EU region | going up today (D17) |
| 2 | One thing the agent does unprompted, **working in the deployed version** | [roadmap.md](roadmap.md) — shortlist only | open ([Q1](open-questions.md)) |
| 3 | Our answers to the practice questions, **with citations** | [practice-questions.md](practice-questions.md) — nine of them | unanswered; who and when is [Q2](open-questions.md) |
| 4 | **One page on the design** | see below | to write |
| 5 | Five-minute demo, five minutes of questions | this page | rehearse Saturday |

**The one page has four named questions, and answering exactly those four is the job:**
how provenance is stored ([data-model.md](data-model.md)), how we catch stale facts
(we do not — [D4](decisions.md), and say so), how deletion propagates
([D3](decisions.md), [D19](decisions.md)), and where inference runs
([architecture.md](architecture.md#residency)). It is a summary of documents we already
have; do not write it from scratch on Sunday morning.

The brief's fallback — a container they run themselves — had to be claimed on Saturday.
We are not using it: we deploy (D17). After today that escape hatch is gone, which is the
point of deciding it today rather than at 11:00 on Sunday.

## Before we submit

- The Streamlit URL is reachable from outside our network, on a device that is not ours.
- It works for someone who has never seen it: the input is obvious and the first answer
  arrives without anyone explaining anything.
- Extraction has been run, the statements file is in place, and the backend has been
  restarted against it.
- Someone who did not build it has asked it three questions end to end.
- The deployment is in an EU region and we can name the region out loud ([Q3](open-questions.md)).

## The order we show things

Five minutes. Four of these five items are scored slices; the fifth is what makes the
judges believe the other four.

1. **A question with receipts.** Ask something about a decision. Show the answer, then
   expand a claim to the document, the location, and the quoted line. Let them pick the
   claim to expand. For a transcript, land on the utterance — "position in the
   conversation" is the phrase in the brief.
2. **Suggestion versus commitment.** Ask about something that was proposed and never
   agreed. The valuable answer is "X proposed it on <date>; no agreement from the customer
   appears in the record" — with the citation for the proposal, and nothing invented for
   the agreement.
3. **Delete a person.** Let them pick. Run the deletion, show the receipt, then ask about
   that person — and then ask about a decision from the same meeting, which still answers.
   Rehearse on **Kwame Boateng**: that is who the practice set deletes (P7), and they
   picked him because he is a source for the provenance question (P1) — deleting him has
   to leave that answer standing, minus his name.
   Say out loud that this is pseudonymisation and what that does and does not guarantee.
   If they pick a first name the archive gives to two people — "Nadia" — the receipt has
   to name both and say which one was removed and which was left. Deletion never stops to
   ask; it decides and discloses ([D19](decisions.md), [corpus.md](corpus.md)).
4. **The thing it does unasked.** *(TODO: pending the team's choice — see
   [roadmap.md](roadmap.md).)*
5. **What it cannot do.** Short, specific, unhedged. The honest-limits list from
   [roadmap.md](roadmap.md). This is scored.

## Answering the live questions

- **Citations are checked.** A citation that does not resolve to real text in a real
  document costs more than the claim was worth.
- **"The record does not say" is a correct answer** when the record does not say it. It is
  better than a plausible reconstruction, and this corpus is built to reward it.
- **When evidence conflicts, say so and cite both sides.** We have no currency signal, so
  we do not pick a winner. Presenting a conflict as a conflict is the honest move and it
  is the one our architecture supports.
- **Never soften what the record says about RELEX.** The archive is unflattering about the
  vendor on purpose and the judges are the vendor. Reporting it straight is the demo.
- **Do not claim more than we do.** The deletion slice grades "filtered and called
  deletion" at zero — below "filtered and declared as a filter". Overclaiming is the one
  failure mode the rubric prices worse than the gap itself.
- **Do not defend a gap.** Name it, point at the roadmap entry, move on.

## Questions to rehearse against

The nine practice questions are in [practice-questions.md](practice-questions.md).
Answering them with citations is submission deliverable 3, not just practice. What each
one is probing is mapped in [corpus.md](corpus.md) — P9 in particular is the one where a
correct citation plus a wrong conclusion scores nothing.

Beyond those, write our own set covering each rubric slice — including at least one
question whose honest answer is "nobody ever agreed to that", one whose honest answer is
"the record conflicts", and one that lands in a transcript where the speaker is
`Me:`/`Them:` so we hear ourselves say "the record does not name the speaker". The judges'
set will be different; the point is to find where we break, not to memorise answers.

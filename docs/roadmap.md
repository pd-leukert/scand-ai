# Roadmap and honest limits

Two audiences for this page: us, deciding what to build next, and the judges, who award
15% partly for "an honest account of what it cannot do".

## MVP boundary

**In:** document storage, one-shot statement extraction with per-document LLM calls,
the aggregated statements file, a question-answering backend that reads only that file,
a Streamlit UI that shows citations, and deletion by role-class redaction of the
statements file.

**Out:** currency classification, cross-document reconciliation, retrieval, embeddings,
cached summaries, a person registry, multi-user anything, and authentication.

## Planned extensions, in the order we would build them

### 1. Reconciliation pass — closes the currency gap (20%)

A second LLM stage after extraction, over the aggregated statements rather than over
documents. It groups statements by topic and writes down the relationships between them:
which statement supersedes which, which contradict each other, which were retracted. From
those links it assigns each statement a status — current, stale, or never-true.

The distinction the brief cares about falls out of the link type, not the dates: a
statement is *stale* when a later statement supersedes it, and *never-true* when another
statement says it was wrong when recorded. A date sort cannot tell those apart, which is
why this is a reasoning pass and not a sort.

This is the single highest-value thing we are not doing, and as of 2026-09-19 it is the
team's agreed successor to the MVP rather than a maybe — the first thing built once the
answering and deletion paths work. What it is *not* is a date heuristic. See D16.

### 2. Measured context ceiling, then a two-stage answer path

As soon as extraction has run once, count the tokens. If the statements file does not
comfortably fit, the next step is a two-stage answer: the model first sees a compact index
of topics and decisions, then loads the full statements for the ones it selected. This
scales past the context window without introducing embeddings — and therefore without
introducing a second artifact that deletion must cascade to.

### 3. Person registry

Actors become records that statements reference, instead of being described on each
statement. Deletion collapses to a single operation, role history becomes explicit, and
alias handling ("Martin", "M. Silén", "the development manager") gets a home.

## What it cannot do — for the demo, stated plainly

**Deletion is pseudonymisation, not erasure.** We replace a deleted person with a
role-class placeholder and keep their statements, so the decisions around them keep
answering. The consequence is that if only one person of that role appears in a given
meeting, the placeholder identifies them by elimination, and their arguments and quoted
words remain in the record. We chose keeping the record over maximal privacy, deliberately.
See [decisions.md](decisions.md) D3.

**Deletion holds only while the pipeline does not re-run.** Our guarantee is about the
statements file. Re-running extraction over the untouched source documents brings the name
back. A production version needs the tombstone to live upstream of extraction.

**No currency signal.** We do not flag stale decisions and we do not detect records that
were never true. When the evidence conflicts, the honest behaviour is to say the record
conflicts and cite both sides — not to pick one. Anything that looks like a currency
judgement in our output is the answering model improvising, and should be treated as
unreliable.

**Answers are bounded by extraction.** If extraction missed a statement, the agent does
not know it exists and will say the record is silent. We cannot distinguish "the documents
do not say" from "our extraction did not catch it".

**Partly measured context ceiling.** The source corpus is ~363k characters — on the order
of 90k tokens, which is why the brief says it fits in a long context window. What we do
*not* know is the size of the statements file derived from it, and that is the number that
decides whether D2 holds. Measure it the first time extraction runs.

**Identity is resolved by a model, not by a registry.** One person appears under two
spellings and two people share a first name, and until extension 3 below exists there is
no canonical person record — only whatever extraction wrote on each statement. A missed
variant is a person who is half-deleted. See D19.

**Six transcripts have utterances we cannot attribute.** Three internal recordings label
speakers `Me:` / `Them:` and three others contain `Unknown Speaker`. We report those as
unknown. This is correct behaviour, but it means some real commitments in the archive are
unattributable by us, and an answer about who agreed in an internal meeting may be
"the record does not name the speaker" when a human reading the room could guess.

**Attribution is only as good as the documents.** Where a transcript does not say who
spoke, or an email thread is quoted without headers, the actor is unknown — and we would
rather report it unknown than guess.

## The thing it does unasked (15%)

> **Still open as of 2026-09-19** — tracked as Q1 in
> [open-questions.md](open-questions.md). What is written below is the shortlist and the
> evidence, not a choice.

The constraint, from the brief: it has to be genuinely unprompted, and it has to be
**working in the deployed version** — a slide does not count. The brief offers four
directions and says the archive supports all four:

1. **Flag where the project has drifted** from what was actually agreed.
2. **Brief someone joining on Monday** on what they need before their first meeting.
3. **Notice a contradiction when a new document arrives** and say so at that moment.
4. **Answer within what the asker is allowed to see** — the same question has different
   correct answers for an account manager, an implementation consultant and someone from
   the partner firm.

What the archive actually supports, cheapest first:

- **(4) is the best fit for what we already have.** Three transcripts are marked
  `INTERNAL` and one `PARTNER`; the internal ones contain deal margin, a named retention
  risk about an individual and candid talk about the customer's staff. A role switch in
  the UI that changes which statements are in scope is a few hours' work on top of the
  statements file, it demonstrates on stage in ten seconds, and it is *deletion-shaped*:
  it is a property of the derived artifact, not a prompt instruction. The catch is that it
  looks like query-time filtering, which is the thing the deletion slice punishes — so we
  would have to be precise about why that is legitimate here and not there.
- **(3) is the strongest story and the most work.** It needs ingestion of a new document
  during the demo plus the reconciliation pass we have not built (extension 1). If
  reconciliation lands early, this is the one that wins the slice.
- **(2) is nearly free once answering works** — a fixed brief generated at startup — but
  it is the least distinguishable from "a search engine with footnotes".
- **(1) depends on reconciliation** as much as (3) does, without the demo moment.

Whoever picks: write the entry in [decisions.md](decisions.md), update
[demo.md](demo.md) step 4, and say what we rejected.

### A fifth candidate, proposed: flag what was meant to be private

> **Proposed, pending the team's agreement — see [decisions.md](decisions.md) D28.**

The agent flags statements that were meant to be private. Extraction marks each statement
`none`, `personal` or `confidential`: private details of someone's life, a speaker asking
that it not be shared or written down, or commercially sensitive terms. When an answer draws
on one, the agent says so without being asked, and shows the receipt.

The archive earns this one. Its `INTERNAL` transcripts contain "do not put that in any shared
document", terms given to another customer, and an executive's family circumstances — and a
plain summariser repeats all of it. It uses only what is already in the statements file, so it
adds no second derived artifact and nothing new for deletion to reach.

Limits, stated plainly. The judgement is the model's, so it will miss some and over-flag
others. A request that refers to something said earlier only works when both are in the same
extraction batch. And it flags; it does not protect. The statement is still in the file, and
whether an answer should withhold the detail is not decided.

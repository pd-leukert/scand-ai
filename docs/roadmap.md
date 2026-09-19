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

This is the single highest-value thing we are not doing, and it is the first thing to
build if the MVP lands early.

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

**Unmeasured context ceiling.** The whole statements file goes into context. We do not yet
know how close 45 documents put us to the limit.

**Attribution is only as good as the documents.** Where a transcript does not say who
spoke, or an email thread is quoted without headers, the actor is unknown — and we would
rather report it unknown than guess.

## The thing it does unasked (15%)

> **Proposed, pending the team's agreement — see [decisions.md](decisions.md) D19.**

The agent flags statements that were meant to be private. Extraction marks each statement
`none`, `personal` or `confidential`: private details of someone's life, a speaker asking
that it not be shared or written down, or commercially sensitive terms. When an answer draws
on one, the agent says so without being asked, and shows the receipt.

The archive earns this one. Its `INTERNAL` transcripts contain "do not put that in any shared
document", terms given to another customer, and an executive's family circumstances — and a
plain summariser repeats all of it.

Limits, stated plainly. The judgement is the model's, so it will miss some and over-flag
others. A request that refers to something said earlier only works when both are in the same
extraction batch. And it flags; it does not protect. The statement is still in the file, and
whether an answer should withhold the detail is not decided.

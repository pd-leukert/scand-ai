# Roadmap and honest limits

Two audiences for this page: us, deciding what to build next, and the judges, who award
15% partly for "an honest account of what it cannot do".

## MVP boundary

**In:** document storage, one-shot statement extraction with per-document LLM calls,
the aggregated statements file, a reconciliation pass that groups statements by topic and
derives a link-based status for each (D31), a question-answering backend that reads only the
derived files, a Streamlit UI that shows citations and their status, and deletion by
role-class redaction of both derived files.

**Out:** retrieval, embeddings, a person registry, multi-user anything, and authentication.

## Planned extensions, in the order we would build them

### 1. Reconciliation pass — closes the currency gap (20%) — **built, D31**

A second LLM stage after extraction, over the aggregated statements rather than over
documents. It groups statements by topic and writes down the relationships between them:
which statement supersedes which, which corrects which, which contradict each other, which
answer which. From those links code derives each statement's status — current, stale,
never-true, disputed or unresolved — and the ids that justify it travel to the citation.

The distinction the brief cares about falls out of the link type, not the dates: a
statement is *stale* when a later statement supersedes it, and *never-true* when another
statement says it was wrong when recorded. A date sort cannot tell those apart, which is
why this is a reasoning pass and not a sort. The one date it reads is a guard that rejects
a `supersedes` link running backwards in time; it creates no status.

It landed before deletion did, which is the cost D31 states plainly: two derived artifacts,
one of them holding model-written prose. Still to do: run it once on the real corpus and
tune its two gates (`RECONCILE_MAX_UNTAGGED`, `RECONCILE_MAX_TOPICS`), whose thresholds are
guesses until then.

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

**Our currency signal is a floor, not a guarantee.** A statement is flagged stale,
never-true or disputed only because a model wrote a link to another statement that exists;
the links are checked against real statement ids, never trusted on sight, but a link the
model did not write is a link we do not have. Untagged statements, topics too large for one
call and links across the cut all fail the same way: the statement is reported `current`.
`current` means only that nothing we grouped with it contradicts it — it does not mean the
record is right. The opposite error exists for `unresolved`: a missed answer leaves an
answered proposal flagged as never answered. When the backend is switched to the statements
file there is no signal at all, and it says so instead of calling everything current.

**The topic summaries are model-written prose, and the hardest thing for deletion to
redact.** The reconciled file holds a one-sentence summary per topic and a note per problem,
written by a model and quoted by nobody. They are exactly what the rubric's deletion band
calls "cached summaries", and a deleted name in one of them is not a span a match will find.
If deletion is not built against both derived files, we stop writing the prose (`KEEP_PROSE`)
rather than claim a deletion we do not have. See D31 and CLAUDE.md rule 4.

**Answers are bounded by extraction.** If extraction missed a statement, the agent does
not know it exists and will say the record is silent. We cannot distinguish "the documents
do not say" from "our extraction did not catch it".

**Partly measured context ceiling.** The source corpus is ~363k characters — on the order
of 90k tokens, which is why the brief says it fits in a long context window. What we do
*not* know is the size of the reconciled file derived from it, and that is the number that
decides whether D2 holds. The extraction job now prints both file sizes and a token estimate
at the end of every run. The first measurement, four documents on a small laptop model, was
a 95 kB reconciled file and a 56k-token prompt, which overran Ollama's default 4096-token
context and was silently truncated. Set the context length explicitly, and expect the full
corpus not to fit in one prompt (D31).

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
  during the demo, plus running the reconciliation pass (extension 1, now built) over it
  without redoing the whole record. That second part is not built. If it lands early, this
  is the one that wins the slice.
- **(2) is nearly free once answering works** — a fixed brief generated at startup — but
  it is the least distinguishable from "a search engine with footnotes".
- **(1) depends on reconciliation** as much as (3) does, without the demo moment. Its
  supersedes links now exist.

Whoever picks: write the entry in [decisions.md](decisions.md), update
[demo.md](demo.md) step 4, and say what we rejected.

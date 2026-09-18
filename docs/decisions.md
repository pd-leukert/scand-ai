# Decision log

Running log of decisions that were genuinely contested — where a reasonable person would
have chosen differently, or where we knowingly accepted a cost. Append, never rewrite:
if a decision is reversed, add a new entry that supersedes the old one and mark the old
one accordingly. (The irony of keeping a decision log with provenance and supersession for
a project about decision logs with provenance and supersession is not lost on us.)

**Anyone working in this repo, human or agent, adds an entry here when they make a call
that was not already written down.** If you found yourself weighing two options, that is
an entry. Cost of writing one: two minutes. Cost of not: the Sunday conversation where
nobody remembers why.

Entry format: number, date, status, the decision, what we rejected, why, what it costs us.

---

## D1 — 2026-09-18 — Accepted
**Per-document extraction, aggregated into one statements file.**

Each document is processed independently by the LLM; the results are concatenated into a
single derived artifact. Rejected: corpus-wide extraction in one pass (does not fit in
context), and pairwise cross-document analysis at extraction time (quadratic, and we do
not have the time).

*Cost:* no extraction call can see that a later document reversed an earlier decision.
This is the direct cause of D4.

---

## D2 — 2026-09-18 — Accepted
**The whole statements file goes into the answering model's context. No retrieval.**

Rejected: retrieval or embedding-based selection of relevant statements. Rejected for the
MVP because embeddings are a second derived artifact that deletion would have to cascade
to, and because we do not yet know how large the statements file actually is.

*Cost:* a hard ceiling we have not measured. If 45 documents produce more statements than
the context window holds, this design stops working and we will know late. Mitigation:
measure the token count as soon as extraction runs once, and treat it as a stated limit in
the demo rather than a surprise. Candidate successors, in order of preference: a two-stage
scheme where the model first sees a compact index and then loads the statements it needs;
retrieval with embeddings only if that is not enough.

---

## D3 — 2026-09-18 — Accepted
**Deletion redacts a person to a role-class placeholder in the statements file.**

A deleted person's name is replaced with `[former RELEX employee]` or
`[former customer employee]` as appropriate, everywhere it occurs — actor fields, agreed-by
parties, and inside verbatim spans. The statements themselves survive, so the surrounding
decisions keep answering. The system discloses that a deletion has occurred rather than
pretending the record was always anonymous.

Rejected:
- *A UUID placeholder* (`person_a7f3`). Same re-identification problem as below, with none
  of the readability, and a UUID-shaped hole visibly reads as a query-time filter.
- *Dropping every statement by or mentioning the person.* Strongest privacy story,
  but it takes the neighbouring decisions with it, and "then keep answering" is half the
  deletion score.
- *Purging the source documents.* Destroys the corpus and makes the deletion demo
  one-shot.

*Cost, stated plainly:* this is pseudonymisation, not erasure. If only one RELEX
consultant appears in a given meeting, `[former RELEX employee]` identifies them by
elimination, and the surrounding content — their role, their arguments, their quoted words
— is untouched. We are betting that the judges value the decision record surviving over
maximal privacy, and we say so out loud rather than claiming a stronger guarantee than we
have. This belongs in the honest-limits section of the demo, not hidden.

*Conditions this decision depends on:* no re-extraction after a deletion, and no second
derived artifact. Both hold today. If either changes — a summary cache, embeddings, a
re-run of the pipeline — this decision has to be revisited, because the name comes back.

---

## D4 — 2026-09-18 — Accepted
**Currency is out of scope for the MVP.**

We do not classify statements as stale or never-true, and we do not link statements that
supersede or contradict each other. Rejected: a date-sort heuristic, which the brief
explicitly says catches only one of the two cases and would let us report a never-true
record as merely old.

*Cost:* 20% of the rubric, knowingly. Chosen because a half-working currency signal that
mislabels a never-true record is worse than a stated gap — it corrupts the provenance
story, which is worth more. Planned successor: a second LLM pass over the aggregated
statements that groups them by topic, writes explicit supersedes/contradicts links, and
assigns a status. See [roadmap.md](roadmap.md).

---

## D5 — 2026-09-18 — Accepted
**Citations point at document + page/line + verbatim span.**

Rejected: document-only citations (does not answer "where in it"), and quote-only
citations with a text search in the UI (fragile against the model paraphrasing, and
whitespace in PDFs).

*Cost:* extraction has to track location through PDF parsing, which is the fiddliest part
of the pipeline and the most likely thing to be wrong under time pressure.

---

## D6 — 2026-09-18 — Accepted
**Speech-act type, actor, and role-as-of-that-document are captured at extraction time.**

Rejected: letting the answering model classify proposal-vs-commitment per query. That
gives different answers to the same question on different days, and the judges ask a
different question set than the practice one.

---

## D7 — 2026-09-18 — Superseded by D10
**No technical specifications until the dataset is in hand.**

No JSON schema, no endpoint definitions, no file layouts written down yet. The shape of
the real documents — how transcripts mark speakers, whether email threads are one file or
many, how status reports are structured — will change all of them.

*Cost:* implementation starts with a design step instead of a written contract. Accepted
because a wrong contract written today gets followed by three services and a coding agent.

---

## D8 — 2026-09-18 — Accepted
**Single Verda VM, docker compose, local Ollama. No external model APIs.**

*Cost:* inference speed is bounded by one VM. If extraction over 45 documents turns out to
be too slow, moving Ollama to a separate Verda GPU instance is the escape hatch and
changes nothing above the configuration layer.

---

## D9 — 2026-09-18 — Accepted
**`uv` for Python dependency management and execution, in every service.**

One tool across all three containers, lockfile committed. Rejected: pip plus venv
per service (slower, and three slightly different setups by Saturday).

---

## D10 — 2026-09-18 — Accepted — Supersedes D7 for the answering path
**Fixed the statement contract now, ahead of the real dataset, to unblock the backend.**

D7 deferred every schema until the corpus was in hand. But the backend's `/query` endpoint
needed something concrete to read, so we fixed the field shape data-model.md already
specifies — id, document_id, location (page/line-range), verbatim_span, actor
(name/organization/role), agreed_by, speech_act, statement_date, document_date — as a
Pydantic model in `backend/src/app/statements.py`, and wrote a hand-built mock statements
file to the same shape so the endpoint has something real to load.

Rejected: the simpler three-field shape (who / what / when) that was first proposed for
the mock. It cannot produce a valid citation — no document id, no location, no verbatim
span — which fails CLAUDE.md's "never invent a citation" rule outright, and drops the
speech-act field requirement 2 (suggestion ≠ commitment) depends on. Building the mock to
the documented shape instead was zero extra cost and kept the mock honest about what
extraction will actually have to produce.

*Cost:* this is still a guess about document structure — page numbers, line ranges and
per-document-type location shape may not survive contact with the real 45 documents, and
extraction has not been built against this contract yet. D7's underlying caution (the real
corpus will change the shape) stands; what changed is that we needed *a* contract to build
the answering path against, and picked the one already reasoned about in data-model.md
over inventing a new one. If the real shape diverges, that supersedes this entry, not D7.

---

## D11 — 2026-09-18 — Accepted
**`/query`: statements delivered to the model as base64, citations resolved server-side
against the trusted file, never taken from the model's own output.**

The statements file is base64-encoded and put in a user message for the answering call,
per direction from Niek. Rejected: plain JSON in the message. Base64 is worse on every
axis that matters for accuracy — roughly 33% more tokens, and it requires the model to
decode text before it can quote from it, which local Ollama models will do unreliably.
Kept anyway because we can fully neutralise the accuracy risk without changing the
transport: the model never gets to assert a citation's document/location/verbatim_span
directly. It tags claims inline with bracket markers (`[1]`, `[2]`, ...) and, after a fixed
delimiter (`===CITATIONS===`), lists the statement ids those markers refer to. The backend
looks each id up in its own copy of the statements file — loaded straight from disk, never
round-tripped through the model — and builds the citation object from that. An id the
model invented, or corrupted while decoding, resolves to nothing and is silently dropped
rather than shown. This is what makes rule 1 ("no citation rather than an approximate one")
true by construction instead of by hoping the model behaves.

Rejected also: asking the model to reproduce the full citation (document id, location,
verbatim span) itself, then trusting it. Same hallucination surface as free-text citations
generally, just wrapped in JSON — the whole reason for the id-lookup indirection is to
remove verbatim-text reproduction from the model's job entirely.

*Cost:* if the model never emits the delimiter line, or emits ids we can't parse, the
answer comes back with zero citations rather than a partial set — the honest failure mode,
but it means a confused model produces an uncited wall of text, not an error we can
surface distinctly from "the record is silent." Also: base64 is still burning tokens and
degrading answer quality for no benefit we've identified; if that shows up in testing, drop
it and send plain JSON instead — the citation-resolution mechanism does not depend on the
encoding.

**Streaming**, added because it was cheap given the design above: the prose answer is
streamed live over SSE as `token` events, token-by-token from the upstream OpenAI-like
completion. Citations are held back — never streamed — until the reply is complete, then
resolved through the same validation gate and sent as one final `citations` event. Rejected:
streaming the raw model output straight through, which would put an unvalidated citation
marker in front of a judge before we've checked it resolves to anything real. The buffering
keeps a safety margin equal to the delimiter's length so the delimiter can't leak a
fragment of itself if it lands across two upstream chunks.

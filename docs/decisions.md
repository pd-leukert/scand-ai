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

## D7 — 2026-09-18 — Accepted; partly superseded by D15
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

## D10 — 2026-09-18 — Accepted
**Python 3.12 across the workspace, pinned at the repo root.**

The three services and the devcontainer image already said 3.12, but the workspace root
had no `.python-version`, so `uv sync` at the root built the venv from whatever the
machine's default interpreter was — 3.14 on one of ours. Local runs and container builds
were on different interpreters.

Rejected: moving everything to 3.14. It is the better interpreter, but the bump touches
the devcontainer image, `requires-python` and ruff's `target-version`, and it buys us
nothing this weekend.

*Cost:* we are a release behind, and a 3.13+ idiom someone copies from a docs page will
work in their editor and fail in the container. The pin is one file to change when we
want the bump.

---

## D11 — 2026-09-18 — Accepted
**One Dockerfile per service, but every image builds from the repository root.**

Each service keeps its own Dockerfile next to its code. The build context is the repo root:
the image copies `uv.lock` and all three member manifests, then syncs only its own package
(`uv sync --locked --package backend --no-install-workspace`, then the code, then a second
sync). Dependencies land in a layer that our source edits do not invalidate.

Rejected:
- *A build context per service folder.* Requires either a lockfile per service or a step
  that copies the root lockfile in — the first contradicts D9's one committed lockfile, the
  second is a build that reaches outside its own context anyway.
- *One shared image running all three.* Cheaper to build, but it erases the service
  boundaries CLAUDE.md asks us to keep, and the extraction job would ship Streamlit.

*Cost:* `docker build` from inside a service folder does not work — builds go through
`docker compose build`, or `docker build -f backend/Dockerfile .` from the root. And
touching any one service's `pyproject.toml` busts the dependency layer of all three images.

---

## D12 — 2026-09-18 — Accepted
**Extraction is a compose job the other two wait on; the statements file is a named volume.**

`statement-extraction` runs to completion and exits 0. `backend` and `frontend` declare
`depends_on: { condition: service_completed_successfully }`, so compose does not start them
until it has. The statements file lives in a named volume, mounted read-write into
extraction and **read-only** into the backend — the artifact has exactly one writer.

Rejected:
- *A bind mount of `./data` on the host.* Easier to inspect during the demo, but it puts
  the derived artifact in the working tree, where it can be committed by accident or
  half-deleted by hand — and the deletion demo depends on the artifact having one
  authoritative state.
- *Starting all three together and having the backend wait for the file itself* (an
  entrypoint poll loop, or a healthcheck that fails until the file exists). That is
  application code whose only job is startup ordering, and compose already expresses it.
- *Letting the backend serve before extraction finishes.* It would answer from an empty
  record, which is the one thing the answering path must not do.

*Cost:* two. Inspecting the artifact from the host now needs `docker compose exec` or
`docker cp`, not `cat`. And any `docker compose up` re-runs the extraction job before the
backend returns — which is correct once extraction is real and expensive, and annoying
before then. The escape hatch for a backend-only restart is
`docker compose up --no-deps backend`.

---

## D13 — 2026-09-18 — Accepted
**The first compose file has three services: no Ollama, and no document mount.**

Ollama is in [architecture.md](architecture.md) as a fourth container and is deliberately
not in `compose.yaml` yet. Nothing in the three skeletons calls a model, and adding the
service means pinning a model name before we have seen the dataset — which the model-as-
configuration rule (CLAUDE.md) and D7 both argue against. The source documents are not
mounted either: extraction fetches the corpus at runtime from external shared storage, so
the pile does not need to be a volume.

Rejected: wiring Ollama in now with a placeholder model so the compose file matches the
architecture diagram. A placeholder model name is exactly the hardcoded model the working
agreement forbids, and an unused service that pulls multi-gigabyte weights slows every
`compose up` between now and the day we need it.

*Cost:* `compose.yaml` and the architecture diagram disagree until extraction actually
calls a model. Whoever adds inference adds the Ollama service and its `OLLAMA_HOST`
configuration in the same change.

---

## D14 — 2026-09-19 — Accepted
**Commercial model APIs are for development only; everything that ships is produced locally.**

The RELEX-provided API key may be used for brainstorming, coding, and iterating on the
extraction prompt and parser against the corpus. The corpus is synthetic, so nothing
sensitive leaves. What is deployed on Verda — the extraction run whose output becomes the
statements file, and the answering path — uses local Ollama only. Which endpoint and model
each stage calls is configuration, so moving between them is a config change, not a code
change.

This narrows D8 and the working agreement's "no external model APIs" rather than
contradicting them: both still hold for the shipped system.

Rejected:
- *Shipping a statements file extracted with a commercial model.* The claim we want to make
  in the demo — everything is processed locally, on our private cloud — would be false of
  the very artifact the judges use.
- *Keeping the ban absolute during development.* It ties prompt and parser iteration to the
  speed of one VM (D8's own cost) for a corpus where nothing is at stake.

*Cost:* prompts tuned against a commercial model may not transfer, and a small local model
may extract noticeably worse — which we learn late unless we test early. The final
extraction run has to be Ollama on Verda and be checked against the practice questions
before anyone relies on it. The commercial key must never reach a deployed image or the
compose file.

---

## D15 — 2026-09-19 — Accepted
**The statement record layout is drafted from the real documents; locations are computed by code, not by the model. Partly supersedes D7.**

D7 held back all schemas until the dataset was in hand. It is now: 45 plain `.txt` files,
23 transcripts, 20 email threads and 2 report threads. The record layout for extraction is
in [data-model.md](data-model.md). Endpoints and the backend API stay unspecified.

The model returns only the verbatim span. Code finds that span in the source text and
derives the line range and the human-readable position (a transcript timestamp, or
"message n of N" counted from the top of the file). A span that is not found verbatim drops
the statement rather than being cited approximately.

Rejected:
- *The model copies a position tag from the chunk, and we check the tag occurs in the
  source.* That check passes for a tag that belongs to a different passage. It verifies the
  tag exists, not that it points at the claim, and a real-looking wrong citation is the
  failure the judges look for.
- *Numbering email messages chronologically.* It disagrees with the file, which is in
  reverse order, so a judge cannot check it by eye.

*Cost:* extraction recall drops whenever the model tidies whitespace or corrects an
obvious speech-recognition slip in a span. We accept that, because a missing statement surfaces as
"the record does not say" while a bad citation costs marks. Teams transcripts interleave
speaker and timestamp lines between the words of a turn, so the matcher has to normalise
across them — fiddly, and the first thing to test. We also keep both a `claim` and a `span`,
so deletion has two free-text fields to sweep, not one.

---

## D16 — 2026-09-19 — Accepted
**Documents are parsed into speaker turns and messages; a statement lies within one; speakers the file does not name stay unnamed.**

`statement_extraction/src/app/documents.py` turns each file into units — one speaker turn in
a transcript, one message in an email or report thread — and every line keeps its number
in the source file. A statement's span has to lie inside one unit, so its actor is never
ambiguous. Positions are what a judge can find by eye: the elapsed time written on the
transcript segment (`1 minute 27 seconds`), `message n of N` counted from the top, and
`line n` in the `INTERNAL` transcripts, which have no timestamps. Parsing fails loudly on
anything it does not recognise, including a thread whose header count disagrees with the
messages found.

The corpus has speakers the file does not name: `Unknown Speaker`, `Guest 1` (13 turns in the
data-protection review) and a dial-in phone number. They get no name, and the label is kept
as written. One named speaker is spelled `Henrik Sorensen` in two turns of a transcript
whose attendee list says `Henrik Sørensen`; the parser keeps it as written.

Rejected:
- *Fixed-size word chunks with position tags the model copies.* They cut across speaker
  changes, so a statement can straddle two people and take the wrong actor.
- *Guessing who `Guest 1` is.* In the data-protection review it is probably the data
  protection officer, but the file does not say, and we would rather report unknown than
  guess (see the roadmap's honest limits).
- *Merging `Henrik Sorensen` into `Henrik Sørensen` in the parser.* That is alias
  resolution, which is a person registry's job (roadmap, item 3), and doing it silently in
  one place would hide the problem from deletion.

*Cost:* a backchannel from someone else ("Mm-hm.") splits one speaker's sentence into two
units, and each half is extracted separately or missed. Units are also small, so extraction
has to batch several per model call while keeping their identity. And the spelling variant
is a warning for deletion: a sweep for `Sørensen` misses `Sorensen`, and names also appear
in email addresses and signature phone numbers.

---

## D17 — 2026-09-19 — Accepted
**A quoted span must appear in the unit it is attributed to, and the stored span is the source's own text.**

`find_span` in `statement_extraction/src/app/matching.py` takes a unit and the span the model
claims to quote, and returns the file line range, the position and the matched text — or
nothing. Only whitespace and Unicode composition may differ: a line break inside a turn, a
doubled space, an accented letter written as two characters. The record stores the text as
it stands in the source, never the model's copy. A quote that starts or ends inside a word or
a number does not match, so `3` is not found in `3.4`. The model names the unit it quoted, and
the search runs only inside that unit. The same text twice in one unit gives the first
occurrence.

Rejected:
- *Fuzzy matching, or accepting a near match above a threshold.* It lets a corrected number
  or a completed sentence through, which is the invented-source failure the brief warns about.
- *Folding quotes and dashes.* The corpus has no curly quotes and no non-breaking spaces, and
  five em dashes, so it would be code for a case that does not occur.
- *Searching the whole document for the span.* A short span such as "Yeah." lands on the wrong
  turn and cites the wrong speaker.

*Cost:* a statement is dropped whenever the model rewords, tidies a speech-recognition slip,
or leaves out a word inside the span, so recall depends on how well the prompt gets the model
to copy exactly — unmeasured until extraction runs. A repeated line inside one unit gets the
first line number, which may not be the one the model meant. And the matcher proves the words
are there, not that they support the claim; that stays a prompt and review problem.

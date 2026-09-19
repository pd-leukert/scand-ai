# Decision log

Questions we have *not* answered yet live in [open-questions.md](open-questions.md), not
here. This file is for calls that were made.

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

## D5 — 2026-09-18 — Accepted *(location clause superseded by D14)*
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

## D7 — 2026-09-18 — Superseded by D20
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

## D13 — 2026-09-18 — Accepted *(document-delivery clause superseded by D18; no-Ollama clause superseded by D27)*
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
**The Streamlit chat UI calls `/query` non-streaming (`stream: false`), not the SSE path.**

`/query` already supports token-by-token streaming for the prose answer. Rejected: parsing
the `text/event-stream` response by hand and rendering it incrementally. Doable, but it is
real code — buffering `token`/`citations`/`done` SSE frames inside Streamlit's
script-rerun model — for a UX gain that does not pay off yet: there is no answering model
running behind `/query` to make a blocking wait feel slow, and the frontend's only job
right now is proving the wire-up between the two services works, with citations rendered
per claim.

*Cost:* once Ollama is wired up, the chat will feel blocking for the length of one full
answer instead of appearing token by token. Revisit then — the backend side of streaming
already exists, so this is a frontend-only follow-up, not a new capability to build.

---

## D15 — 2026-09-19 — Accepted
**`DUMMY_LLM=true` skips the model call and answers from the loaded statements file
directly, so `/query` (both the plain and SSE paths) can be tested without Ollama.**

Needed a way to exercise the real wire contract — SSE framing, inline `[n]` markers, the
server-side citation-resolution step — while nothing calls a real model yet (D13). Picked:
a config flag, checked in `config.py` alongside `LLM_BASE_URL`/`LLM_MODEL`, that swaps in a
canned answer built from the first few statements in whatever file is already loaded, then
runs that answer through the *same* `_resolve_citations` function a real model's output
goes through. Rejected:
- *A hardcoded fixture in the frontend.* Tests nothing about the backend's SSE framing or
  citation resolution, and puts response-shaping logic in the one place CLAUDE.md says
  must hold none.
- *A separate `/query/dummy` endpoint.* Two routes to keep in sync with the real contract,
  for a distinction the frontend and the judges' traffic should never need to make.

Because the dummy path still calls `_resolve_citations` against the trusted file, it can't
emit a citation that isn't real even though no model produced it — the same guarantee rule
1 asks for, just exercised without inference.

*Cost:* one more branch in `answer_question`/`stream_answer_question` to keep in sync with
the real path if the response shape changes. Remove it once Ollama answers are the only
thing anyone needs to test against.
**Citations locate a claim by line range plus a genre-specific pointer. D5's PDF clause is
retired.**

The archive arrived: 45 plain-text files, no PDFs, no attachments
([corpus.md](corpus.md)). D5 assumed "page and line for PDFs, line range for text files"
and named PDF parsing as the fiddliest part of the pipeline. That part does not exist.
D5 otherwise stands — document + location + verbatim span is still the citation — this
entry only replaces how the location is expressed:

- **line range** in the file, for everything;
- **plus the utterance offset** for transcripts (`Marco Rossi 1 minute 4 seconds`, already
  printed by the Teams export) — the brief asks for "a position in the conversation" and
  this is one, free;
- **plus the message within the thread** for email threads and status reports, because one
  file holds up to eighteen messages from five people across months.

Rejected: *line range alone* (points at a whole thread, which is the document-only
citation D5 already rejected, one level down), and *byte or character offsets* (exact, but
a judge checking a citation by hand cannot use them — the receipt has to be readable by
the person holding it).

*Also settled by the archive landing:* D7's condition is met, so contracts can be written
as code gets built. *Not* settled: D13 says extraction fetches the corpus from external
shared storage and `compose.yaml` mounts nothing, while the archive now sits in `input/`
in the working tree. Whoever wires extraction picks one and writes the entry.

*Cost:* three location shapes instead of one, and the frontend has to render each of them
as something clickable. Cheaper than PDF page mapping, and it is the difference between a
citation and a filename.

---

## D15 — 2026-09-19 — Superseded by D19
**Deletion targets a resolved person, not a name string. A deletion request that is
ambiguous is confirmed before it runs, not guessed.**

The corpus contains two planted identity traps ([corpus.md](corpus.md)): one person under
two spellings (`Henrik Sørensen` / `Henrik Sorensen`), and two different people sharing a
first name (`Nadia Haddad`, who is everywhere, and `Nadia Öberg`, mentioned once — the two
are told apart in exactly one line of one internal transcript). The judges pick who gets
deleted, and both traps sit directly on the 20% deletion slice.

So the deletion operation takes a person, and a person is a set of surface forms confirmed
before anything is redacted:

1. The request resolves to the surface forms found in the statements file — every
   spelling, and first-name-only references where they are unambiguous.
2. If the resolution is ambiguous, **the system asks which person** and redacts nothing
   until it is told. "Delete Nadia" has two correct answers and no safe default.
3. Redaction then covers every resolved form, in actor fields, in agreed-by parties, and
   inside verbatim spans (D3).

Rejected:
- *Replacing the literal string the requester typed.* The obvious implementation, and it
  fails both traps: `Henrik Sorensen` survives a delete of `Henrik Sørensen`, and deleting
  `Nadia` takes a bystander with it. Half a deleted person is a failed deletion slice, and
  a deleted bystander is a failed "keep answering everything else".
- *Unicode-folding names and matching loosely.* Catches Sørensen/Sorensen, makes the
  collision worse, and silently over-redacts wherever two names are close.
- *Asking the model to decide who was meant, per deletion.* Non-deterministic on the one
  operation the judges test adversarially.

*Cost:* deletion is no longer one function call — it needs a resolution step, and where
identity is genuinely ambiguous it needs a human answer, which we have to show in the demo
rather than hide. We are treating the confirmation prompt as a feature: being asked "which
Nadia?" is evidence the system knows the archive contains two. Until the person registry
exists ([roadmap.md](roadmap.md), extension 3) this resolution runs over the statements
file each time, which is the boring version and fine at this size.


---

## D16 — 2026-09-19 — Accepted
**Currency stays out of today's MVP. The agreed successor is a second-pass LLM layer that
groups statements and evaluates them — not a date heuristic, and not nothing.**

Revisited because three of the nine practice questions are currency questions (P5, P6, P9)
and P9 cannot be answered at all without the stale/never-true distinction. D4 stands for
what ships today; what changes is that the reconciliation pass is now the team's agreed
direction rather than a roadmap maybe, and it is the first thing built after the MVP
lands.

Rejected:
- *Pulling reconciliation into today's MVP.* 20% is a lot, but the answering path and the
  deletion path are worth 45% between them and neither works yet. A half-built
  reconciliation pass that mislabels a never-true record damages the provenance story,
  which is the thing we are actually good at.
- *Conflict detection only* — surfacing that statements on a topic disagree, with both
  sides cited, without classifying which is current. Genuinely tempting as a middle path,
  and it is what the answering prompt should do anyway when the record conflicts. Rejected
  as a *separate* build step because it is most of the grouping work of the full pass with
  none of the payoff; the grouping is the expensive half.
- *A date sort.* Forbidden by the working agreement, rule 5, and by the brief.

*Cost:* unchanged from D4 — 20% of the rubric, knowingly, plus P9 answerable only by
accident. What we buy is that the gap is a stated boundary with a designed successor,
which is what the initiative slice's "honest account of what it cannot do" rewards.

---

## D17 — 2026-09-19 — Accepted
**We deploy to the Verda VM today and submit a URL. The container-handover fallback is not
used.**

The brief allows "a container we can run" instead of a URL, but only if we tell them on
Saturday — today. Choosing now rather than discovering on Sunday morning that nothing is
reachable. The URL goes up as soon as there is a frontend to put behind it, stub backend
or not, and everything after that is a redeploy into a thing that already works.

Rejected:
- *Container handover.* Safest technically, but the brief says "Submit a URL, not a repo",
  and grading is the judges using it themselves for an hour. A tarball reads as not
  finishing.
- *Deploying late, on Sunday.* The standard way to lose the whole submission.

*Cost:* someone spends part of today on deployment instead of features, and we no longer
have the fallback — after today, telling them we cannot host is not an option.

*Open, and blocking the submission:* nobody has confirmed the **EU region** of our Verda
VM. Residency is scored and "it is Verda" does not answer "where". Confirm it and write it
into the one-page design document.

---

## D18 — 2026-09-19 — Accepted
**The archive is baked into the extraction image at build time. This supersedes D13's
document-delivery clause.**

`COPY input/ …` in the extraction Dockerfile. The build context is already the repository
root (D11) and `.dockerignore` does not exclude `input/`, so this is one line and no
compose change. D13's "extraction fetches the corpus at runtime from external shared
storage, so the pile does not need to be a volume" no longer holds; the rest of D13 (no
Ollama service yet) is untouched.

Rejected:
- *A read-only bind mount of `input/`.* Equally boring and easier to swap a document into,
  but the running system then depends on a checkout being present next to it on the VM,
  and the deployed container stops being self-contained.
- *Fetching from Verda object storage at runtime* (D13 as written). Matches the "documents
  live in EU storage" story, but it puts credentials and a network call into the one job
  the whole demo depends on, and it fails on Sunday morning in a way nothing else does.

*Cost:* changing a document means rebuilding the image, which is correct for an archive
that is fixed for the weekend and wrong for anything else. The archive ships inside the
image, so that image does not go to a public registry — the corpus is synthetic, but
residency is scored and the habit is the point. And `input/` has to be committed for the
build context to contain it.

---

## D19 — 2026-09-19 — Accepted *(supersedes D15)*
**Deletion resolves a person to all their surface forms and never prompts. On an ambiguous
name it removes the best-evidenced match and says, in the receipt, who it removed and who
it left.**

D15 had the system stop and ask which person was meant. Reversed: deletion stays a single
non-interactive operation the judges can fire and walk away from, because that is how they
test it — they pick a person, run it, then ask questions. An operation that halts on a
dialogue is an operation that looks broken in someone else's hands.

What survives from D15, unchanged: **a person is not a string.** Resolution still happens
first, still covers every surface form (`Henrik Sørensen` / `Henrik Sorensen`), and still
redacts actor fields, agreed-by parties and verbatim spans (D3).

What replaces the prompt: a deterministic pick, not a model judgement. Among candidates
matching the requested name, the one with the most statements in the statements file wins;
an exact full-name match beats a first-name match outright. Then **the receipt names every
candidate considered and what happened to each.** For the corpus we have, "delete Nadia"
removes Nadia Haddad (hundreds of statements) and reports that Nadia Öberg, mentioned
once, was left — which is the right outcome and is visible as a decision rather than a
silent one.

Rejected:
- *Prompting on ambiguity* (D15). Correct-but-unusable: the judges are not expecting a
  conversation, and a deletion that needs a second interaction is a deletion that can be
  half-done.
- *A pre-built person registry with a dropdown*, which removes ambiguity at request time.
  It is the right long-term shape (roadmap extension 3), but it is a second derived
  artifact, and adding one means making deletion cascade to it in the same change —
  working agreement, rule 4. Not today.
- *Replacing the literal string typed.* Fails both planted traps: `Henrik Sorensen`
  survives a delete of `Henrik Sørensen`, and deleting `Nadia` takes a bystander with it.

*Cost, stated plainly:* a wrong pick deletes a person who did not ask to be deleted and
leaves the one who did. Our mitigation is disclosure, not prevention — the receipt shows
the choice, so a judge can see it and correct it by naming the full name instead. On this
corpus the evidence gap between the two Nadias is enormous, so the pick is safe here and
would not be on an archive with two equally present people. Say that out loud in the demo.

---

## D20 — 2026-09-18 — Accepted *(supersedes D7 for the answering path; renumbered from D10, which was already taken)*
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

## D21 — 2026-09-18 — Accepted *(renumbered from D11, which was already taken)*
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

---

## D22 — 2026-09-19 — Accepted
**The frontend is reached through Coolify's proxy, not a published host port. It declares
`expose: 8501` and `SERVICE_FQDN_FRONTEND_8501`.**

D17 committed us to submitting a URL, and the URL comes from Coolify's reverse proxy. The
proxy needs to be told which service and which container port the domain belongs to; it
does not infer that from a compose file. `ports: "8501:8501"` published Streamlit straight
onto the VM's public interface and left the proxy with nothing to route, so the deployment
came up healthy and the domain served nothing. `expose` keeps the port on the compose
network, and the `SERVICE_FQDN_FRONTEND_8501` variable — passed through unset, filled in by
Coolify — is what generates the route. The backend is unaffected: it was never published
and still is not.

Rejected:
- *Keeping `ports` and assigning the domain in the Coolify UI.* Works, but the routing then
  lives in a web form nobody else on the team can see, and the compose file in the repo
  stops describing how the thing is actually reached. It also leaves 8501 open on the
  public interface, bypassing TLS, for anyone who finds the IP.
- *Publishing the port and submitting `http://<vm-ip>:8501` as the URL.* No TLS on a URL
  judges will be asked to type, and a bare IP reads as unfinished.

*Cost:* `docker compose up` on a laptop no longer serves the frontend on localhost:8501 —
local work needs `docker compose run --service-ports frontend`, or running Streamlit
outside the container as `frontend/README.md` already describes. And the deployment now
depends on a Coolify-specific variable name, which is a lock-in we accept for the weekend;
moving hosts means changing this block.

---

## D23 — 2026-09-19 — Accepted
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

## D24 — 2026-09-19 — Accepted
**The statement record layout is drafted from the real documents; locations are computed by code, not by the model. Builds on D20, which replaced D7.**

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

## D25 — 2026-09-19 — Accepted
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

## D26 — 2026-09-19 — Accepted
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

---

## D27 — 2026-09-19 — Accepted
**Extraction calls Ollama over HTTP; Ollama and the real job are wired in separate compose layers until the job has run once. Partly supersedes D13.**

`statement_extraction/src/app/extract.py` posts to Ollama's `/api/chat` with `httpx`, which the
service already has, asking for JSON that matches a schema, at temperature 0 and with thinking off (a thinking
model can spend its whole budget reasoning and return nothing, as the 0.8B one did). The model, host,
context size and batch size come from the environment; `EXTRACTION_MODEL` has no default
(D23). The model is asked for a unit number, a span, a claim, an act, who agreed, and the
speaker's organisation and role — and nothing else. The actor is taken from the unit by code.
An organisation or role is kept only if those words are in the attendee list or the unit, and
`agreed_by` keeps only people who appear in the document. Units are batched by a word budget
and never split, which refines D1: still one document at a time, in several calls when it is
long. The budget defaults to 300 words. On the 4B model one 1000-word batch stopped covering the
document (22 statements kept, 28 thrown away), while three 300-word batches kept all 48 in the
same total time.

The Ollama service, the model download and the real command are in
`compose.extraction.yaml`; the GPU reservation is in `compose.gpu.yaml`. `compose.yaml` is
unchanged. There is no cache of model output, a failed call fails the job, and the statements
file is written whole or not at all. Statements thrown away are counted by reason on stdout and
not stored.

Rejected:
- *The `ollama` Python package.* A dependency for one POST request.
- *Ollama in the base `compose.yaml` now.* Anyone running `docker compose up` to work on the
  frontend would wait on a model download, and be blocked.
- *Asking the model for the actor, the position or the line numbers.* It cannot be trusted to
  copy them; code has them (D24, D25, D26).
- *Retrying failed calls, or caching output per document.* Retries hide a flaky run, and a cache
  is a second derived artifact that deletion would have to reach (working agreement, rule 4).
- *Storing the rejected model output for inspection.* It would hold names the redaction never
  sees.

*Cost:* three compose files to remember, until the job has run for real and the layers fold into
`compose.yaml` and the placeholder command goes. The archive is read from `input/`, which
the extraction Dockerfile copies into the image as D18 says, so nothing is mounted. A call that fails late
loses the run, with no resume. And the prompt has not met a real model yet, so recall and the
share of statements thrown away are both unknown.

---

## D28 — 2026-09-19 — Proposed
**The thing the agent does unasked: flag statements that were meant to be private.**

Extraction gives every statement a `handling` value: `none`, `personal` (private details of
someone's life) or `confidential` (a speaker asks that it not be shared or written down, or it
is commercially sensitive). When an answer draws on a `personal` or `confidential` statement,
the agent says so without being asked and shows the receipt. Chosen because the archive's
`INTERNAL` transcripts contain exactly this — "do not put that in any shared document", terms
given to another customer, an executive's family circumstances — and extraction faithfully
recorded all of it, as a summariser would repeat it. It uses only what is already in the
statements file, so it adds no second derived artifact and nothing new for deletion to reach.

Proposed by one team member; it becomes Accepted when the team agrees.

Rejected:
- *Detecting agreed-then-never-done items across documents* (practice question P8). A stronger
  demo, but it needs the cross-document pass that D4 defers.
- *Dropping sensitive statements at extraction.* The record would lose real content without
  saying so, which is the opposite of what this project is for.

*Cost:* the judgement is the model's, so it will miss some statements and over-flag others,
and the same one may be marked differently on two runs. A request such as "do not put that in
any shared document" refers to the line before it, so it only works when both are in the same
extraction batch. And this flags, it does not protect: the statement stays in the file and in
the receipt. Whether an answer should withhold the detail is an open question.

---

## D29 — 2026-09-19 — Accepted
**Who agreed is found in a second pass over the statements, and every agreement points at the statement where it happened.**

The first extraction pass no longer asks the model for `agreed_by`. On real runs it left it empty
in all 67 statements, including a plain "Confirmed" in reply to a request (email 07, practice
question P3). A second pass, `link_agreements`, takes each proposal or question and the next
eight statements by other people, in time order (a thread lists its newest message first), and
asks whether one of them accepted it, rejected it, or nobody answered. The model names the
responder and quotes their words. The link is kept only if that person has a later statement
containing the quote. Each entry in `agreed_by` is `{name, label, statement}`: `statement` is the
id of the agreeing statement, so "who agreed" has a receipt the way a quote does, and `label`
holds what the file calls a speaker it does not name. The pass runs over extracted statements
at extraction time, not over source documents, and writes into the same file, so there is no new
artifact.

Rejected:
- *Asking for it in the first pass.* Already tried; the model never filled it in.
- *Matching words such as "yes" or "confirmed".* It misses paraphrase ("that works for us") and
  fires on a yes that answers a different point.
- *Keeping names without the statement id.* An agreement nobody can check.
- *Storing refusals.* They are counted but not stored yet.

*Cost:* one more model call per proposal or question, a few hundred to over a thousand on the
full corpus. The quote check proves the words exist in that person's statement, not that they
answer this proposal: in the test on email 07, two of three links were right and one attached a
"Confirmed" that was about a different point. A reply more than eight statements away is missed.
Candidates are picked by the first pass's label, so a request labelled `report` is never linked:
when the full job ran on the same email, the model merged "It must be excluded at source before
the next extract runs" into the sentence before it as a `report`, and only two links were found,
one right and one doubtful (Kwame's "Answer on the historic files", taken as agreeing to a
different request). Both wobbles came from a 4B model and may be smaller on a bigger one.
So an empty `agreed_by` now means no answer was found nearby, not that none exists. It is also the
place a wrong "who agreed" could reach an answer, so the answering side should cite the agreeing
statement whenever it says someone agreed.

---

## D30 — 2026-09-19 — Accepted
**The statements file is one JSON object, `{"statements": [...]}`, not JSON Lines. Supersedes the JSONL choice in the D24 layout.**

The record layout drafted with D24 called for JSON Lines, and the Docker image's default was
changed from `statements.json` to `statements.jsonl` to match, without a log entry. Neither had
a reason behind it. The job writes the file once, whole or not at all, and the answering side
reads it whole (D2), so nothing uses appending, streaming or line-by-line recovery, which is
what JSONL is for. The backend on `niek/backend` loads one JSON object of exactly this shape,
and the original Dockerfile default was already `.json`. So extraction now writes
`{"statements": [...]}` to `statements.json`, indented so it reads and diffs by eye.

Rejected:
- *Keeping JSONL and changing the backend to read lines.* More change on the other side for no
  gain.
- *Writing both.* A second copy of the derived artifact, and a second place a deleted name would
  survive (working agreement, rule 4).

*Cost:* it is one JSON document, so it can only be read whole. A truncated file would be
unreadable rather than partly usable, which the write-then-rename already prevents. If the file
ever grows too big to read whole, JSONL is the way back. The field names still differ from the
backend's; see blocker 2 in [whats-left.md](whats-left.md).

---

## D31 — 2026-09-19 — Accepted
**The statements file uses the backend's field names, and what the backend cannot hold is written as text. Supersedes the field names in the D24 layout.**

`statement_extraction/src/app/output.py` converts each record just before the file is written:
`doc_id` becomes `document_id`, `span` becomes `verbatim_span`, `act` becomes `speech_act`,
`lines` becomes a `location` with `line_start` and `line_end`, and the dates become
`statement_date` and `document_date`. The backend's own loader on `niek/backend` reads real
output from the job as it is, with no change on Niek's side. That was checked on real runs: a
transcript with unnamed speakers, an email, a report, and an email with linked agreements. The
extra fields (`position`, `claim`, `handling`, `doc_type`, and a `label` on each speaker) ride
along, and the loader ignores them. The extraction code keeps its own names; only the written
file changes.

The backend requires a name, an organisation and a role, as strings, for every speaker. Where the
archive gives none: a speaker the file does not name is shown by the label the file uses ("Them",
"Guest 1"), with `label` set so it can be told from a real name, and an organisation or role that
no document states is `Not stated`.

Rejected:
- *Writing nulls.* Honest, and what D24 said, but the backend rejects the whole file on one until
  its model changes.
- *Waiting for the backend to change first.* It leaves the chain blocked on one reply, with the
  deadline tomorrow.
- *Renaming inside the extraction code.* Churn in the code and its tests for no gain: one function
  at the boundary does it.

*Cost:* a `name` can hold a label, and `Not stated` is a string a consumer could mistake for a
fact. The answering prompt already says to use organisation and role as recorded, so it should
read `Not stated` as no information. Once the backend accepts null, the conversion goes back to
nulls in one place (`_actor`). Deletion also gets more places a name can sit: `name`, each
`agreed_by` name, the quote and the claim.

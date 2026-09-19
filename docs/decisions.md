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

## D13 — 2026-09-18 — Accepted *(document-delivery clause superseded by D18)*
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

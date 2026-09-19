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

## D14 — 2026-09-19 — Superseded by D27
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

## D23 — 2026-09-19 — Accepted *(supersedes D13's Ollama clause)*
**Ollama is a compose service with a GPU reservation and a named model volume, and the
model is pulled by a one-shot job that everything calling a model waits on.**

D13 kept Ollama out of `compose.yaml` until something actually called a model, and said
whoever added inference adds the service and its configuration in the same change. The
backend now calls one (D21), so this is that change. The service mirrors the container we
had been starting by hand on the VM — `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`,
`OLLAMA_KEEP_ALIVE=30m`, all GPUs reserved — so nothing about the runtime changes, only who
starts it. Backend and extraction reach it at `http://ollama:11434/v1` over the compose
network; the loopback publish of `127.0.0.1:11434` is kept so `ollama` and `curl` still
work when SSH'd into the VM, and it stays off the public interface, which is the same line
D22 draws for the frontend.

The model name is still not hardcoded: `LLM_MODEL` and `EXTRACTION_LLM_MODEL` are separate
variables with `qwen3.8:27b-mtp-bf16` as the default for both, and the two are independent
because the working agreement says never assume extraction and answering use the same one.

**The pull is a job, not a step someone remembers.** `ollama-pull` runs `ollama pull` for
both models against the server and exits; `statement-extraction` and `backend` both wait
on `service_completed_successfully`. Rejected:
- *Pulling by hand after deploy* (`docker exec ollama ollama pull ...`), which is what we
  did during setup. It works exactly once, on a VM someone has a shell on, and it is
  invisible to anyone reading the compose file. A judge redeploying, or any of us on
  Sunday, gets a backend that starts healthy and 404s on the first question.
- *An entrypoint script in the backend image that pulls on boot.* That is startup logic in
  application code, which D12 already rejected for the statements file, and it puts the
  pull in the request path's container.
- *Baking the weights into an image.* Tens of gigabytes per build, and the model stops
  being a configuration value.

*Cost:* three. A cold `compose up` now blocks on a multi-gigabyte download before anything
answers — bounded, since a re-pull of a present model is a no-op, but the first deploy on a
fresh volume is slow and the failure mode is a job that sits there looking hung. The GPU
reservation makes the compose file refuse to start on a machine without an NVIDIA runtime,
so laptop work means running the model elsewhere and overriding the base URLs. And the
model store is a named volume (`ollama-models`), not the `/root/ollama-data` bind we used
by hand — a VM that already has the weights there either re-downloads them or has the
directory copied into the volume once.

---

## D24 — 2026-09-19 — Accepted
**The laptop/server switch is an override file, `compose.dev.yaml`, not an environment
variable. It swaps in a small model and drops the GPU reservation.**

Wanted: a laptop runs a tiny model, the VM runs the real one, and nobody edits a file to
move between them. The obvious shape is a single env var set on the server, and it does
not work — not because it is inelegant, but because the blocker on a laptop is the GPU
reservation, not the model name. A machine without the NVIDIA container runtime refuses
the container outright (`could not select device driver "nvidia"`), and a device
reservation cannot be disabled by interpolation: we tested `count: ${GPU_COUNT:-0}` and
the reservation is still sent and still fails. The `deploy` block has to be *absent*, and
only a merge can remove a key. So the switch is a file:

```
docker compose -f compose.yaml -f compose.dev.yaml up --build   # laptop
docker compose up --build                                        # VM, unchanged
```

`compose.dev.yaml` uses `deploy: !reset null` to delete the reservation, `volumes:
!override` to swap the VM's weights bind for a named volume, and re-points both model
variables at `qwen3:0.6b` (~520 MB). Verified on a laptop with no NVIDIA runtime: Ollama
starts CPU-only, the healthcheck passes, the pull job exits 0, and
`POST /v1/chat/completions` returns a well-formed answer — the small model is a *reasoning*
model, but Ollama puts that in a separate `reasoning` field and leaves `content` clean, so
the `===CITATIONS===` parsing in `llm_client.py` is unaffected.

Rejected:
- *A single `SCAND_ENV` variable on the server.* What the user asked for and what we tried
  first. Cannot remove the GPU reservation; see above.
- *An env var for the model plus a file for the GPU.* Two mechanisms for one switch, and
  the failure mode is picking one and forgetting the other.
- *`compose.override.yaml`*, which compose loads automatically. That is the frictionless
  version on a laptop and a trap on the VM: Coolify deploys the repo, and a file that
  applies itself silently would put a 0.6B model in front of the judges.

The direction is deliberate: the base file is the server, and the laptop opts out. A
forgotten flag locally fails loudly with a device-driver error; a forgotten flag on the VM
is not possible, because there is no flag to forget.

*Cost:* local work is a longer command. `DEV_LLM_MODEL` overrides the small default, and
`LLM_MODEL`/`EXTRACTION_LLM_MODEL` still win over both, so pinning a mid-sized model for a
realistic local test stays a one-off env var. And answer *quality* at 0.6B is not
representative — the dev stack proves the wiring works, never that a prompt is good enough.

---

## D25 — 2026-09-19 — Accepted *(supersedes D24)*
**Inverted: the compose defaults are a laptop, and the VM sets three environment
variables. `compose.dev.yaml` is deleted.**

D24 made the base file the server and had laptops opt out with `-f compose.dev.yaml`. The
reasoning was that a device reservation cannot be disabled by interpolation, which is true
and still is. What it missed: `deploy.resources.reservations.devices` is not the only way
to ask for a GPU. `runtime:` is a plain scalar, so it *can* be interpolated —
`runtime: ${OLLAMA_RUNTIME:-runc}` is off by default and becomes a GPU by setting one
variable. That removes the reason the switch had to be a file.

So the defaults are now the laptop, and `docker compose up` with no arguments, no flags and
no `.env` gets a CPU-only stack on `qwen3:0.6b`. The VM sets three variables:

```
OLLAMA_RUNTIME=nvidia
OLLAMA_DATA_DIR=/root/ollama-data
LLM_MODEL=qwen3.8:27b-mtp-bf16
```

Three and not five, because two things were measured rather than assumed. `OLLAMA_DATA_DIR`
defaults to `ollama-models`, a bare name compose reads as a named volume, and an absolute
path turns the same line into a bind mount — one variable covers both. And
`OLLAMA_FLASH_ATTENTION=1` with `OLLAMA_KV_CACHE_TYPE=q8_0` turn out to be harmless on a
CPU-only host (llama.cpp reports `flash_attn = enabled`, a q8_0 KV cache, and serves
normally), so the GPU tuning is unconditional and is not part of the switch.
`EXTRACTION_LLM_MODEL` defaults to `${LLM_MODEL}`, so the one model variable covers both
paths while either can still be pinned alone.

Rejected: keeping D24's file and adding an env var for the model only — two mechanisms for
one switch, the thing D24 itself rejected. Also rejected: `COMPOSE_FILE` in a gitignored
`.env`, which gives the same zero-argument laptop run but only after each dev creates a
file, and invisibly.

*Cost, and it is the real one:* D24's best property is gone. It said "a forgotten flag on
the VM is not possible, because there is no flag to forget" — now there are three, and
partial states are silent rather than loud. `OLLAMA_RUNTIME` alone gives a GPU serving a
0.6B model; `LLM_MODEL` alone starts a 27B model on CPU, which will not fail, just crawl;
and a missing `OLLAMA_DATA_DIR` re-downloads ~54GB into a fresh volume instead of erroring.
None of these announce themselves. Verified on a laptop with no NVIDIA runtime: the
defaults pull the small model and answer over `/v1/chat/completions`. **Not** verified:
`runtime: nvidia` on the VM — `docker run --gpus all` working does not prove a named
`nvidia` runtime is registered with the daemon, because `--gpus` uses a different code
path. Check `docker info | grep -A3 -i runtimes` on the VM before trusting this; if
`nvidia` is not listed, run `nvidia-ctk runtime configure --runtime=docker` and restart
the daemon, or revert to D24's file-based switch.

---

## D26 — 2026-09-19 — Accepted
**`ollama-pull` prints its resolved configuration and warns on the two half-set states.
Confirms D25's cost rather than reversing it.**

D25 traded away the one property D24 had — "there is no flag to forget" — and named the
consequence: three independent variables, and partial states that are silent. The first
real deploy hit it immediately. Coolify had `OLLAMA_RUNTIME=nvidia` but not
`OLLAMA_DATA_DIR`, and the log said only `Volume ollama-models Creating`. Nothing was
wrong enough to fail; it was simply about to re-download ~54GB it already had on disk.

So the pull job now prints runtime, model store and both model names as a banner before it
pulls, and warns on the two combinations that are wrong rather than merely unusual: a GPU
runtime with no `OLLAMA_DATA_DIR` (re-downloads the weights), and a 27B-class model on the
`runc` runtime (runs, but far too slowly to demo). Both were tested against all four
laptop/VM permutations.

Rejected: *failing the job on a half-set config.* Tempting, and wrong — every one of these
combinations is legitimate somewhere. A GPU host with no existing weights genuinely should
download them, and a big model on CPU is a reasonable thing to try once. Turning a slow
configuration into a failed deploy on the Sunday of a hackathon is worse than a loud line
in a log. Rejected also: *deriving the variables from each other* so only one has to be
set. They are independent on purpose — the whole reason D25 works is that
`deploy.resources.reservations.devices` was replaced with a scalar an environment variable
can turn, and coupling the three back together rebuilds the thing D24 got stuck on.

*Cost:* the warnings are pattern matches on model names (`*27b*`, `*70b*`, `*qwen3.8*`), so
a big model named something else slips through unwarned, and the list needs editing when
the model changes. A banner is also only as useful as the person reading the deploy log.

**Separately, and the reason the deploy failed at all:** `runtime: nvidia` requires a named
runtime registered in the daemon, which this VM did not have. `docker run --gpus all`
works there because `--gpus` uses device requests, a different code path — so the toolkit
being installed never implied the runtime was registered. Fixed on the host with
`nvidia-ctk runtime configure --runtime=docker` and a daemon restart, not in the repo. D25's
verification note already said to check this; it is recorded here because the check came
back negative and the fix lives on the machine, where the repo cannot show it.

---

## D27 — 2026-09-19 — Accepted — Supersedes D14
**The Streamlit UI now calls `/query` with `stream: true` and renders tokens live via
`st.write_stream`, reversing D14.**

D14 deferred this because nothing answered `/query` yet, so a blocking wait couldn't feel
slow. D15's `DUMMY_LLM` changed that — there is now a real, working SSE producer to test
against, including its per-token pacing (`DUMMY_LLM_DELAY_SECONDS`), and D14's non-streaming
call meant that pacing was invisible: the frontend waited for the whole response and painted
it in one frame regardless of how the backend staged it. Rejected: keeping `stream: false`
and adding an artificial `time.sleep` before returning, which fakes a wait without proving
the actual SSE path — the frame types, the citation-withholding-until-`done` behaviour — is
wired correctly end to end.

Implementation: `stream_backend()` parses the `text/event-stream` body into `(event, data)`
pairs by hand (`requests` has no SSE client), yields `token` text to `st.write_stream`, and
stashes `citations`/`error` into a plain dict passed by reference, since `write_stream` only
wants a string generator. The hero's ask form is held in an `st.empty()` so it can be
cleared the instant a submission is detected, rather than sitting above the streaming answer
for the run's duration — cosmetic, but two visibly different pages open at once is not
"boring" either.

*Cost:* the SSE parser is hand-rolled and untested against a real Ollama stream — `_sse()`
on the backend and this parser have to keep agreeing on the wire format, and nothing
currently pins that beyond D15's dummy path and manual testing. If the frame format ever
changes, both sides need updating together.

---

## D28 — 2026-09-19 — Accepted
**The real extraction job is ported in from a teammate's parallel branch
(`shah/extraction-pipeline`), adapted to this branch's names and contracts, rather than
rewritten from scratch or merged wholesale.**

`statement_extraction` was a placeholder — it started, served `/health`, and exited after a
minute; nothing read the corpus or called a model. A teammate had, independently, already
built the real thing against the same brief: corpus parsers for all three genres
(`documents.py`), a verbatim-span matcher that only accepts a quote if it is actually in the
unit, untouched (`matching.py`), per-document structured-output extraction against Ollama's
native `/api/chat` (`extraction.py`), an agreement-linking pass that gives every `agreed_by`
entry a receipt statement, and 62 tests — including tests that run the parsers against the
real `input/` corpus and assert facts checked by hand (23/20/2 documents, the
Sørensen/Sorensen spelling split, the three `Me`/`Them` internal transcripts).

Rejected:
- *Writing extraction fresh against this branch.* All of the above already exists, tested,
  against our own corpus. Redoing it duplicates real work for no gain, and the parsing code
  in particular — regex-driven, three date languages, doubled Teams timestamps — is exactly
  the fiddly kind of code corpus.md warns is where the traps live.
- *Merging the branch wholesale.* It restructures `compose.yaml` into separate
  `compose.extraction.yaml`/`compose.gpu.yaml` files and rewrites `docs/decisions.md`
  wholesale, renumbering everything from D23. Both conflict directly with D18–D27 as they
  stand on this branch. A wholesale merge would have to resolve those by hand anyway, with
  more surface area at risk than porting the application code alone.

What was changed in the port, and why:
- **Env var names.** The source branch read `EXTRACTION_MODEL`/`OLLAMA_HOST`/
  `STATEMENTS_PATH`. This branch already documents `EXTRACTION_LLM_MODEL`/
  `EXTRACTION_LLM_BASE_URL` (statement_extraction/README.md, D23) and `STATEMENTS_FILE_PATH`
  (backend/README.md, config.py) — `extract.py` now reads those instead, so `compose.yaml`
  did not need to change at all. `EXTRACTION_LLM_BASE_URL` carries `/v1` for the backend's
  OpenAI-compatible path; this job calls Ollama's native API instead, so it strips the
  suffix rather than asking compose to carry two URLs for one host.
- **The prompt gained the placeholder trap.** data-model.md is explicit that a statement
  must never be built from an attachment placeholder (four forms, including a bare `Image`
  and a Swedish one), a signature block, or the synthetic-data banner. The ported prompt did
  not mention any of this — nothing stopped the model turning `[Image removed by sender]`
  into a report. Added one paragraph naming all four forms plus signature blocks and the
  banner. Everything else in the prompt and schema (the `claim`/`handling` fields, the
  agreement-linking pass) is carried over exactly.
- **Location gained a `position` field; see D29.**
- **The container runs the script directly instead of a FastAPI server; see D30.**

*Cost:* the port was reviewed and adapted, not independently re-derived — correctness for
the parts left unchanged (the regex parsing, the span matcher, the linking heuristic) rests
on the source branch's own tests plus a fresh run of the full suite against this repo's
`input/`, not on a second implementation to compare against. The `claim` and `handling`
fields ride along in the written JSON unused by the backend today (Pydantic drops unknown
fields); they cost nothing at rest, but they are surface area nobody has decided to build
on, and a future entry should either give them a job or drop them.

---

## D29 — 2026-09-19 — Accepted *(extends D20's interim shape)*
**`Location` gains an optional `position` field: the utterance offset for a transcript, or
"message N of M" for an email thread or status report — D14's genre-specific pointer,
nested inside `location`, not a sibling field.**

D14 fixed what a citation's location has to carry — line range everywhere, plus a
genre-specific pointer, because a thread's filename alone points at up to eighteen messages.
D20's mock-file shape predates D14 and only has `page`/`line_start`/`line_end`; nothing
wired the pointer through, so a real extraction run would have had it in hand and then
dropped it before it reached a citation. Fixed now, as the real extraction job lands, by
adding `position: str | None` to `backend/src/app/statements.py`'s `Location` model —
`Citation` reuses `Location` directly, so the field reaches `/query` and the frontend
without touching `schemas.py`. `frontend/app.py`'s `location_label()` appends it after the
line range when present.

Rejected: *a top-level `position` field on the statement*, which is what the ported
extraction code did before this entry. D14 frames the pointer as part of "where in it," the
same question the line range answers — a judge checking a citation should find both in one
place, and a second top-level field is a second place the frontend has to remember to read.

*Cost:* none identified — the field is optional, so the existing mock file and any statement
without a meaningful position (nothing currently produces one outside extraction) validate
unchanged.

---

## D30 — 2026-09-19 — Accepted
**The extraction container's `CMD` runs `python -m src.app.extract` directly and exits. It
no longer starts a FastAPI server.**

The placeholder ran `fastapi run` and used a 60-second self-timer to exit 0, because D12
needs the container to be a job — something compose can wait on with
`service_completed_successfully` — and a FastAPI/uvicorn server does not exit on its own.
architecture.md's stated reason for making extraction a service rather than a script was to
support triggering re-extraction of a single document without a redeploy; that endpoint was
never built, so the server was carrying a real dependency (`fastapi[standard]`,
`uvicorn[standard]`) and a real bug shape (the self-timer) for a feature that does not exist.
Running the extraction script as the container's command does exactly what D12 already
committed to, with nothing standing in for a job that isn't one.

Rejected: *keep the FastAPI wrapper and call the extraction job from its lifespan, then
exit.* Works, but it is a web framework imported and installed for a process that serves no
request, wrapping a call that would otherwise just be the entrypoint.

*Cost:* the re-extraction-without-redeploy capability architecture.md described is further
off than the placeholder made it look — building it now means reintroducing a server (or a
separate trigger mechanism) on top of `extract.py`'s `main(filters)`, which already accepts
document-id substrings for exactly this, just not over HTTP. Until then, re-running
extraction means `docker compose up --build statement-extraction` or the local command in
statement_extraction/README.md.

---

## D31 — 2026-09-19 — Accepted
**`extract_document` sends a whole document to the model in one call. The
`EXTRACTION_BATCH_WORDS` word-count chunker (`_batches`, default 300 words) is deleted, not
reconfigured.**

The chunker came in with D28's port and split a document's units into runs of ~300 words so
each model call stayed small; D28 doesn't call the number out, it's just what the ported
code did. Direction from Niek: remove it outright rather than raise the default — a
document is 45 files at most a few thousand words each (the largest,
`reports/01_weekly-status-thread.txt`, is ~3,300), well inside a modern local model's
context window, and splitting mid-document means the model extracting unit 40 cannot see
units 1–39: an agreement, a correction, or the attendee list that would have told it a
speaker's org can land in a batch it never gets to read. `extract_document` now builds one
`messages` list from the full unit range and makes one `chat()` call per document; `_batches`
and the `EXTRACTION_BATCH_WORDS` env var are gone, not defaulted differently.

Rejected: *raising the default instead of removing the mechanism.* Keeps a second
context-sizing knob (`EXTRACTION_BATCH_WORDS` alongside `EXTRACTION_NUM_CTX`) whose only
job was working around a limit this corpus doesn't hit, and keeps the cross-batch
blind-spot for any document that still lands over the raised number.

*Cost:* a document that does approach `EXTRACTION_NUM_CTX` (default 8192) no longer has a
chunker to fall back on — the fix is raising `EXTRACTION_NUM_CTX`, documented in
statement_extraction/README.md, not re-adding a splitter. The whole-document prompt is also
a bigger single call than before, so an extraction run trades many small requests for fewer,
larger ones; `EXTRACTION_TIMEOUT` (default 600s) is the relevant dial if that matters on a
slower host.

---

## D32 — 2026-09-19 — Accepted
**The answering path's HTTP client to Ollama gets a configurable `LLM_TIMEOUT` (default
600s), replacing a hardcoded 120s. A mid-stream failure now ends the SSE stream with its
own `error` event instead of dying silently.**

Reported symptom: the frontend showed "Could not reach the backend: Response ended
prematurely" after a long wait on a large model. Traced to
`stream_answer_question`/`answer_question` in backend/src/app/llm_client.py, both of which
opened `httpx.AsyncClient(timeout=120)`. httpx's (and requests') timeout is a *read*
timeout — seconds of silence between chunks, not a cap on the whole call — so this fires
whenever the model goes quiet for over 120s, which a large model does routinely during
prefill of the full statements payload, well before it emits a first token. When it fired
mid-stream, the exception propagated out of the async generator `StreamingResponse` was
iterating; headers and some chunked body were already on the wire, so the ASGI connection
just stopped instead of sending the terminating chunk. The frontend's `requests` client
reads that as a broken chunked encoding — "Response ended prematurely" is urllib3's message
for exactly that, not a requests-level timeout, which is why raising the frontend's own
`REQUEST_TIMEOUT` alone would not have fixed it.

Fix, two parts:
- `Settings.llm_timeout` (`LLM_TIMEOUT` env var, default `600`) replaces both hardcoded
  `timeout=120` call sites. 600s matches `EXTRACTION_TIMEOUT`'s existing default (D31) —
  the same "boring, generous, configurable" shape, not a new pattern.
- `stream_answer_question` now wraps its httpx call in `try/except httpx.HTTPError` and
  yields an `error` SSE event (`{"message": ...}`) instead of letting the exception kill
  the stream uninstructed. The frontend's `stream_backend()` gained a matching
  `elif event_type == "error"` branch that sets `result["error"]`, reusing the error box
  the UI already has for connection failures. This is the same fix even if `LLM_TIMEOUT` is
  raised further and still gets hit, or Ollama returns a 5xx mid-stream: an honest "the
  model did not answer" beats a cryptic transport error, per CLAUDE.md's "fails honestly."
- Frontend's `REQUEST_TIMEOUT` (now `BACKEND_REQUEST_TIMEOUT` env var) raised to `600` to
  match, so it doesn't become the next thing that cuts off a long wait now that the backend
  is configured to tolerate one.

Rejected: *raising the hardcoded value without making it configurable.* Same class of
problem as `EXTRACTION_BATCH_WORDS` before D31 — a number picked for a demo-sized case,
silently wrong for a slower host or a bigger context, with no dial to reach for. Rejected
also: *catching the exception in main.py's `/query` handler.* By the time `StreamingResponse`
is iterating the generator, the response has already started; a handler-level catch can't
turn already-sent chunked output into a clean response. The generator is the only place
that can end the stream on its own terms.

*Cost:* a genuinely stuck Ollama (hung, not just slow) now takes up to 10 minutes to report
as an error instead of 2 — the tradeoff for not cutting off a slow-but-working large model.
`BACKEND_REQUEST_TIMEOUT` and `LLM_TIMEOUT` are two variables that have to be kept in step
(documented in both READMEs, not enforced in code); nothing stops someone raising one and
forgetting the other, same shape of risk D25/D26 already accepted for the runtime switch.

---

## D33 — 2026-09-19 — Accepted
**The answering call to Ollama's OpenAI-compatible endpoint sends `"reasoning_effort":
"none"`, not `"think": false`. Verified against a running local model, not assumed.**

Same motivation as raising `LLM_TIMEOUT` in D32 — a thinking model spends real time
reasoning before it ever emits the answer, and answering here is picking and paraphrasing a
citation, never a problem that benefits from working through steps. extraction.py already
disables this for the same reason (`"think": False`, module docstring's comment on why),
which made `"think": false` the obvious first thing to copy into `llm_client.py`'s
`_request_payload`. It doesn't work: extraction calls Ollama's native `/api/chat`, this
module calls the OpenAI-compatible `/v1/chat/completions` — different endpoint, different
field. Checked directly against `qwen3:0.6b` on the local Ollama: a plain request and one
with `"think": false` both came back with a populated `reasoning` field and
~340-428 `completion_tokens` for a one-word answer; `"reasoning_effort": "none"` came back
with no `reasoning` field and 10 `completion_tokens` for the same question. That field name
mirrors OpenAI's own reasoning-effort parameter, which is presumably why Ollama's
OpenAI-compatible layer honors that name instead.

Rejected: *assuming `"think": false` carried over from D28's ported extraction code and
moving on.* It doesn't error, doesn't warn, and returns a normal-looking response — the
model just keeps reasoning at full length. Silent no-ops like this are exactly what a
30-second empirical check against the real local model catches and a code read does not.

*Cost:* none identified for the current model. If the answering model is ever swapped for
one Ollama's OpenAI-compatible layer maps `reasoning_effort` differently for (or not at
all), this needs re-verifying the same way — this entry is a fact about qwen3:0.6b and
Ollama 0.34.2 on this endpoint, not a guarantee for every model or Ollama version.

---

## D34 — 2026-09-19 — Accepted — Supersedes D33
**`_request_payload` sends `"chat_template_kwargs": {"enable_thinking": false}`, per
docs/qwen_3.8_quickstart.md, instead of D33's `"reasoning_effort": "none"`.**

D33 verified `"reasoning_effort": "none"` against the model actually running in this dev
environment (`qwen3:0.6b`) and it worked — but D33's own cost note already flagged that as
a fact about that one model, not a guarantee for whatever the answering model is deployed
as. The deployed model is different: `LLM_MODEL=qwen3.8:27b-mtp-bf16` in production versus
`qwen3:0.6b` here (D25). docs/qwen_3.8_quickstart.md is that model family's own
documentation, and it says two things D33 didn't know: `reasoning_effort` for Qwen3.8 only
takes `xhigh`/`medium`/`low` — there is no documented off value, so `"none"` was never a
supported setting for the model this actually has to run against, just a value Ollama's
qwen3:0.6b handling happened not to reject. The documented way to fully turn thinking off
is `chat_template_kwargs: {"enable_thinking": false}` (`extra_body` in the doc's Python SDK
examples is the SDK's name for "merge these keys into the top-level request JSON," not a
literal wire field).

Checked what D33's method checked, and it comes back negative: `chat_template_kwargs`
against `qwen3:0.6b` via this repo's Ollama is a silent no-op, same shape as D33's finding
about `"think"` — accepted (200, no error), reasoning unchanged. Expected: `qwen3:0.6b` is
a different, older model line and doesn't speak the Qwen3.8 chat template this key
controls. Kept anyway, on direction from Niek, because the target of the fix is the
production model's documented contract, not what the dev placeholder happens to honor.

Rejected: *keeping D33's `"reasoning_effort": "none"` as a belt-and-suspenders addition
alongside `enable_thinking`.* The doc enumerates `reasoning_effort`'s valid values for this
model family and `"none"` is not among them; a server that validates the enum strictly
could 400 on every `/query` call once pointed at the real model — worse than the thing
being fixed, and on the path that matters most. Sending an unlisted value on a guess is the
exact mistake D33 was written to stop making.

*Cost, and it is real:* unlike D33, this entry's fix is **not verified against the model it
targets** — there is no Qwen3.8-family model in this environment to check it against, only
the dev-default `qwen3:0.6b`, which (as above) can't confirm or deny it. This is asserted
from the vendor doc, not observed. Before relying on it for a demo, run the same check D33
ran — a short prompt, compare `usage.completion_tokens` and the presence of a `reasoning`
field with and without the flag — directly against `qwen3.8:27b-mtp-bf16` on the VM.

---

## D35 — 2026-09-19 — Accepted
**Extraction writes one JSON file per document under `documents/` as it goes, so progress is
visible during a slow run. `STATEMENTS_FILE_PATH` is these files concatenated, and the
directory is deleted once that concatenation succeeds — it is scratch, not a second
artifact.**

Direction from Niek: print/see each document's file as extraction works through the corpus,
and assemble the final file from them at the end. Implementation in
statement_extraction/src/app/extract.py: `_write_json()` (the same atomic tmp-then-`replace`
write the final file already used) writes `documents/<doc_id>.json` right after each
document's `extract_document`/`link_agreements` pass, printing the path; once the loop ends,
those same files are read back and concatenated, in doc-id order, into the final file.

The cleanup is not what was asked for — it's what CLAUDE.md rule 4 requires once the shape
above exists. `documents/*.json` carries the same actor names and verbatim spans as the
derived statements file; left in place permanently, it is a second location deletion would
have to reach, and nothing does — deletion isn't built yet for the *primary* file either, so
there was nothing to "wire in" today, only a gap to leave for whoever builds it. Rather than
leave that gap, the job deletes `documents/` (`shutil.rmtree`, best-effort) right after the
merged file is written. That still delivers the actual ask — the files exist and are
visible for the entire run — without leaving a lasting copy of the data outside the one
place deletion will know to look.

Rejected: *keeping the per-document files permanently for post-hoc debugging.* Real value
(inspecting one document's extraction without rerunning the whole corpus), but it's exactly
the second-artifact shape rule 4 warns about, on a corpus whose whole premise is that
judges test deletion by checking everywhere a person could survive. The debugging value is
also mostly redundant with what already prints to stdout per document (statement count,
drop reasons, agreement-linking responses).

*Cost:* a run that fails outright (every document comes back empty, D30/D31's "must not
look like a finished record" branch) never reaches the cleanup line, so `documents/` is left
behind in exactly that case — deliberately, since a fully-failed run is also the case
debugging most needs the per-document breakdown. A run interrupted partway (killed, crashed)
leaves it behind too, for the same reason. Only a clean, fully-merged run cleans up; anyone
inspecting a stale `documents/` directory after such a run should treat it as leftover from
an earlier failed attempt, not as current.

---

## D36 — 2026-09-19 — Accepted
**The statements file groups statements under their document. `document_id`, `document_type`,
`document_date`, the people involved and a document summary are carried once per document,
not once per statement — `id`, `document_id` and `document_date` are no longer written on
each statement at all, since they are cheaper to derive than to store.**

Direction from Niek: cut the token cost of the statements file, which D2 already flagged as
an unmeasured "hard ceiling" because the whole file goes into the answering model's context
on every question. Every statement previously repeated its full document id (a path like
`transcripts/07_2024-11-12_ordering-logic-design`), its document type and its document date
verbatim — the same handful of strings, once per statement, on documents that run into dozens
of statements each. None of that varies within a document, so none of it needs to.

Shape: `{"documents": [{"id", "type", "date", "people", "summary", "statements": [...]}]}`.
Each entry in `statements` carries only what genuinely varies per statement — `location`
(line range plus D14's genre-specific pointer), `verbatim_span`, `claim`, `speech_act`,
`handling`, `actor`, `agreed_by`, `statement_date` — and nothing document-level. `id` is
gone too: extraction already assigns `f"{doc.doc_id}#{position}"` internally to link
agreements (D28); backend/src/app/statements.py's `load_statements()` now derives the same
string from array position when it flattens the file back into the `Statement` shape
`llm_client.py`, `schemas.py` and the frontend already had — that shape does not change, so
nothing downstream of `load_statements()` had to.

**`people` and `summary` are new, both read off the document rather than invented.**
`documents.py`'s `Document` gains a `summary` field: a transcript's `Meeting:` header line,
or a thread's `Subject:` line (the topmost message's, since threads run newest-first) — the
document's own summary of itself, in its own words, from its first few lines. `people` reuses
the existing `attendees` mechanism: transcripts already had it from the `Attendees:` header;
threads previously left it empty, and now get it populated from the set of actual message
senders, since a thread has no attendee header and "who sent something" is the honest
substitute for "who was in the room."

**The same regrouping is reapplied in `backend/src/app/llm_client.py`, not just in the file
on disk.** The file's shape only pays off if the backend forwards it that way: D2's actual
cost is the payload rebuilt and resent to the model on every question, not the file at rest,
which is loaded once and cached. `_grouped_payload()` regroups the flattened `Statement`
objects back by `document_id` before base64-encoding, so `document_id`/`document_date` still
appear once per document in `STATEMENTS_B64`, not once per statement. Citation resolution
(D21) is untouched: statements still carry their own explicit `id` in this payload, so the
model still cites exactly as it always has — only the JSON shape around each statement
changed, not the trust mechanism.

**What is explicitly *not* dropped, despite an interrupted earlier edit on this branch doing
so:** `location` and `verbatim_span`. Both vary per statement, so hoisting does not apply to
them, and CLAUDE.md rule 1 requires a real location and a real verbatim span on every
citation — cutting either would fail provenance outright, not just shrink the file. A
half-finished diff on this branch had removed both (along with `id`, `document_id`,
`handling`, `agreed_by`, `role` and more) before this entry; that direction is reversed here.
`role` and `agreed_by` are kept for the same reason — they are statement/actor-level, not
document-level, and `agreed_by` in particular is half of requirement 2's score.

Also dropped, deliberately, as real dead weight rather than as part of the hoisting: `label`
on the actor (already folded into `name`, never read separately by anything downstream) and
`location.page` (the corpus has no PDFs — D14 already retired the concept; the field stays on
the backend's `Location` model, defaulting to `None`, since removing it there is a separate,
unrequested schema change).

Rejected:
- *Leaving `document_id`/`document_type`/`document_date` on every statement and only adding
  `people`/`summary` at the document level.* Half the ask — it adds the requested fields but
  does nothing about the repetition that is the actual "massively reduce tokens" complaint.
- *Writing an explicit `id` per statement even after grouping.* Either it repeats the
  document id inside the group (defeats the point) or it's a bare per-statement counter that
  still has to be written and read for no information a reader can't already get by counting
  array position.
- *Stopping at the file on disk and leaving `_build_messages` flattening everything back out.*
  Correct-looking but pointless: the file is loaded once per process (D2's caching); the
  model payload is rebuilt on every question, which is where the token count that motivated
  this actually lives.

*Cost:* `load_statements()` now does real reconstruction work (deriving ids, pulling
`document_id`/`document_date` back onto every `Statement`) instead of a straight parse, and
that reconstruction is now the one place the id scheme (`f"{document_id}#{position}"`) has to
agree with what `extraction.py` computes internally for the exact same purpose — currently
kept in sync by convention (both are "array position, 1-indexed"), not by shared code, since
they live in different services with no shared library between them (D9 keeps them on one
lockfile, not one codebase). If either side's numbering ever changes independently, agreed-by
receipts and citation ids go out of sync silently rather than erroring. `people` for threads
is derived from senders, not a real attendee list (threads have none) — it will list someone
who sent one message and nothing else alongside someone central to the thread, with no way to
tell the two apart from `people` alone.

---

## D37 — 2026-09-19 — Accepted, supersedes part of D36

**A persisted statement carries exactly `claim`, `actor` (`name`, `organization`),
`speech_act`, `statement_date` — nothing else. `location`, `verbatim_span`, `agreed_by` and
`actor.role` are removed from the statements file, from the backend's `Statement`/`Citation`
models, from the answering prompt, and from what the frontend renders.**

Direction from Niek: he asked for exactly this shape for `statements.json`, given as a
literal example with these four fields and no others. I flagged, before making the change,
that it reverses the part of D36 that explicitly kept `location` and `verbatim_span` (D36
called removing them "a half-finished diff on this branch" and reversed it), and that
CLAUDE.md rule 1 requires a citation to point at "a real location... and a verbatim span
that actually appears there" — without them the system can no longer show the receipt the
rubric's provenance slice (25%, [data-model.md](data-model.md)) is built to reward, and
dropping `agreed_by`/`role` cuts into part of the attribution slice (20%) the same document
describes. Niek confirmed he wanted the literal shape regardless. This entry is that
argument, on the record, per CLAUDE.md's "argue in a new entry" rule — it does not overrule
D36's reasoning, it overrides it on this project's owner's explicit instruction.

**What actually changed, concretely:**
- `statement_extraction/src/app/output.py`'s `to_statement()` needed no code change — a
  prior, uncommitted, half-finished edit on this branch had already reduced it to this exact
  shape (the same one D36 reversed). That edit is now the intended final state, not an
  interruption to fix.
- `statement_extraction/src/app/extraction.py` is untouched: it still asks the model for
  `span`, `role`, `handling` and still runs `link_agreements`, and `extract_document` still
  validates a claim's span against the real unit text before accepting it. None of that is
  wasted: span-matching is still extraction's only defence against a hallucinated claim, it
  is just no longer written to the file (`to_statement` already only reads `claim`, `act`,
  `actor.name`/`actor.org`, `stated_on` off the record — "extra fields ride along" per its
  own docstring). Whether to also stop computing `role`/`agreed_by` internally, now that
  nothing downstream reads them, is left open — see Rejected.
- `backend/src/app/statements.py`: `Location` model deleted; `Actor` loses `role`;
  `Statement` and `_StatementBody` lose `location`, `verbatim_span`, `agreed_by`, gain
  `claim: str`.
- `backend/src/app/schemas.py`: `Citation` loses `location`, `verbatim_span`, `agreed_by`,
  gains `claim: str`.
- `backend/src/app/llm_client.py`: the system prompt no longer tells the model statements
  carry a location, verbatim text, role or agreed-by list; rule 2 (agreements/decisions) no
  longer conditions on `agreed_by`, since there is nothing to condition on — the model is
  told to trust `speech_act` alone and never to name a specific agreeing party unless that
  party's own statement is the agreement; rule 3 drops "and role". `_resolve_citations` and
  `_dummy_answer` build citations/sentences from `claim` instead of `verbatim_span`, and
  drop role from the actor description.
- `backend/src/app/data/mock_statements.json`: rewritten to the new shape; each
  `verbatim_span` was turned into a `claim` (a plain-sentence paraphrase, by hand, in the
  style `extraction.py`'s prompt asks the model for) since a claim did not previously exist
  on the mock data.
- `frontend/app.py`: `location_label()` deleted; `render_source_row()` no longer shows role,
  location, or an expand/collapse "Show quote" — there is no verbatim quote left to reveal,
  so the claim is shown inline instead, unconditionally. The agreed-by line is gone.
- `docs/data-model.md`: the provenance and attribution sections now say, per field, whether
  it is still stored, rather than describing a shape the code no longer produces.

**What this costs, plainly:** a citation from this system now points a judge at a document
and a paraphrased claim, attributed to a named person at a named organisation, dated — not
at a real line range and not at a verbatim quote they can diff against the source file. That
is a real reduction against the provenance slice of the rubric this corpus was built to
score, not a cosmetic one. Extraction's span-matching still guarantees the claim is grounded
in real text at extraction time, but that guarantee is no longer independently checkable by
a judge from the output, which was the entire point of carrying the span forward. Deletion
still has one place to reach — the claim replaces the verbatim span as the place a redacted
name can hide (see [data-model.md](data-model.md), "What deletion has to touch") — so CLAUDE.md
rule 3/4 are not affected, only rule 1.

Rejected:
- *Keeping `location`/`verbatim_span` and only trimming `agreed_by`/`role`.* This was the
  first option offered; Niek explicitly chose the fuller cut instead.
- *Also stripping `role`/`agreed_by`/`handling` out of extraction's own schema and prompt,
  and deleting `link_agreements` entirely, since nothing downstream reads their output any
  more.* Not done here — that is a real efficiency win (fewer model calls per document) but
  a separate, larger change to `extraction.py`'s tested internals than "change the output
  shape", and this entry's scope is the persisted/served shape, not extraction's internal
  validation machinery. Left as a known follow-up, not silently decided either way.
- *Renaming `Citation` or its fields to signal it is no longer a verified quote.* Not done —
  out of scope for a schema-shape change and not requested; the cost above is recorded here
  instead of encoded in a new name.

---

## D38 — 2026-09-19 — Accepted
**Fixes a production crash: `EXTRACTION_NUM_CTX`'s default raised 8192 → 32768, and one
document's malformed model response no longer takes down the whole extraction run.**

Reported symptom: the extraction container crashed with an unhandled
`json.decoder.JSONDecodeError: Unterminated string`, in `_ollama_chat`'s
`json.loads(response.json()["message"]["content"])`. Root cause: D31 removed the ~300-word
chunker and started sending a whole document to the model in one call, on the reasoning
that every document in this corpus is small enough to fit — true for the input side, but
D31's own cost note already flagged the output side as unchecked: a document with many
statements needs a correspondingly long schema-constrained JSON response, and input plus
output both draw from the same `num_ctx` budget. Once that budget runs out mid-generation,
Ollama stops — not with an error, just a response cut off wherever it was, which is exactly
what "unterminated string" is: valid JSON up to the point the token budget ended, then
nothing.

Two changes, addressing both what happened and what should happen next time it does:
- `EXTRACTION_NUM_CTX`'s default is 32768, not 8192 — four times the headroom, comfortably
  covering the corpus's largest document (~3,300 words) plus a generous statement count,
  without requiring exotic extended-context support from the model.
- `main()`'s per-document loop now wraps `extract_document`/`link_agreements` in
  `try/except (httpx.HTTPError, json.JSONDecodeError)`. A failure is treated exactly like a
  document that legitimately produced nothing: logged, added to `empty`, given an empty
  `documents/<doc_id>.json` (D35), and the job moves on. The run still fails overall (same
  "a document with no statements is a silent gap" exit-1 path already in place) — this
  isn't hiding the failure, it's refusing to let one bad response erase every other
  document's completed work in the same run.

Rejected: *raising `num_ctx` alone, without the try/except.* Reduces how often this
happens but doesn't change what happens when it still does — some document, some model,
some day, produces more output than any finite budget holds, and D35's whole premise (a
crash shouldn't cost you the documents already done) was only half-built without also
covering documents *not yet reached* when the crash happens.

*Cost:* a document that fails this way now silently contributes zero statements to the
final file rather than stopping the run for a human to look at — the same tradeoff D31 and
D35 already accepted for other empty-document cases, extended to a new cause of emptiness.
The stderr line (`"{doc_id}: extraction call failed (...)"`) is what distinguishes "the
model genuinely found nothing" from "the call broke" in the log; nothing enforces that
distinction downstream, since both feed the same `empty` list and the same exit code.

*Note on numbering:* this entry was committed as "D36" (commit 32ae359), then collided with
a second, unrelated "D36" (statement regrouping, above) added on this branch — a `git stash`
conflict over the same header got committed with its `<<<<<<<`/`=======`/`>>>>>>>` markers
left in place, docs/decisions.md#L1064 through #L1265 in ab4ea32. Every other reference to
the regrouping and claim-only-cut decisions, in code and in docs, already says "D36" and
"D37" for those two, so this entry moves here as D38 rather than the other two moving —
content is unchanged from the original commit, only the number and position are.

---

## D39 — 2026-09-19 — Accepted

**The answering prompt's citation-id example is fixed to the post-D36 id shape
(`"<document_id>#<position>"`, e.g. `"workshop-notes-2026-03-12#1"`), replacing a stale
`["stmt-004", "stmt-011"]` example left over from before D36 renumbered statement ids.**

Reported symptom: citations stopped rendering in the frontend entirely after the D36/D37
schema change, with no exception anywhere in the pipeline — `_resolve_citations`
(llm_client.py) silently drops any id the model emits that isn't in `statements`, by
design (D21), so a citation list of ids that don't match produces zero citations, not an
error. D36 replaced the flat `"stmt-NNN"` ids the mock data used before it with derived
`f"{document_id}#{position}"` ids (statements.py's `load_statements`), but
`llm_client.SYSTEM_PROMPT`'s rule 6 was never updated — its worked example still showed
`["stmt-004", "stmt-011"]`, a shape that now matches nothing in the payload. A small local
model leans hard on a prompt's worked example; presented with real ids that look nothing
like the example, it plausibly reverts to inventing ids in the example's shape instead of
copying the real ones character for character — exactly the failure `_resolve_citations`
was built to swallow silently.

Fix: the prompt's opening statement description now names the id shape explicitly
(document id plus position, with a real-shaped example) instead of just saying "an id",
and rule 6's own example was updated to match. Rule 6 also gained an explicit "copy it
exactly — never shorten it, renumber it, or make one up" instruction, since the failure
mode is the model normalizing an unfamiliar-looking id into something that looks more like
a typical short code.

Rejected: *changing the id scheme back to something shorter instead of fixing the
prompt.* The `document_id#position` shape is what D36 deliberately chose to avoid writing
a redundant `id` field into the statements file — reverting it to shrink the string a
model has to copy verbatim would undo D36's actual point (cutting stored/resent
repetition) to work around a prompt that just hadn't been updated to describe the new
shape.

*Cost:* none identified — this restores the prompt to describing the payload it actually
sends, which is what D21's citation-trust mechanism assumes it does. Not independently
verified against a running model in this change; the fix is inferred from the mismatch
between the prompt's example and the real id format, which is the only place in the
codebase still showing the pre-D36 id shape (confirmed by grepping for `"stmt-"` across
`docs/` and `backend/`).

---

## D40 — 2026-09-19 — Accepted, supersedes part of D21

**`/query`'s statements payload is sent to the model as plain JSON text under
`STATEMENTS_JSON`, not base64 under `STATEMENTS_B64`.**

Direction from Niek, exercising the option D21 itself already left open: D21 chose base64
"per direction from Niek" at the time, while flagging in its own *Cost* section that
base64 costs roughly 33% more tokens and "requires the model to decode text before it can
quote from it, which local Ollama models will do unreliably," and said outright: "if that
shows up in testing, drop it and send plain JSON instead — the citation-resolution
mechanism does not depend on the encoding." D39 (same day) is exactly that symptom: a
plausible explanation for citations silently disappearing was the model mishandling an
encoded payload rather than copying real ids out of it. Moving to plain text removes a
whole failure mode (decode-then-quote) rather than just patching the one example that
happened to be stale.

What changed: `_build_messages` no longer base64-encodes `_grouped_payload`'s JSON dump; it
puts the JSON straight into the user message under a renamed label, `STATEMENTS_JSON`
(the old `STATEMENTS_B64` label described an encoding that no longer happens, so it had to
change too, not just the bytes after it). `SYSTEM_PROMPT`'s opening paragraph no longer
tells the model to decode anything. `base64` is no longer imported. Citation resolution
(D21's actual trust mechanism) is untouched: the model still only ever gets to name an id,
never assert a citation directly, and an id that doesn't resolve is still silently dropped.

Rejected: *keeping base64 and only fixing D39's stale example.* Treats the symptom D39
found without addressing the mechanism D21 already suspected of causing it — if decode
unreliability was contributing to dropped citations, fixing one example string leaves the
rest of that risk in place for the next id shape change.

*Cost:* base64 also functioned as ballast in the prompt — the JSON structure was inert to
the model until decoded, which meant field names like `"claim"` or `"speech_act"` couldn't
accidentally read as instructions embedded in the user turn. Plain JSON reintroduces
whatever prompt-injection-via-statement-content surface that ballast incidentally removed;
untested here, and worth a look if a future document's text is adversarial toward the
prompt itself. Not independently verified against a running model — D39 and this entry are
both argued from the mechanism, not from an observed before/after answer.

---

## D41 — 2026-09-19 — Accepted

**`_build_messages`'s user turn puts `QUESTION` before `STATEMENTS_JSON`, and the JSON
itself is dumped with `separators=(",", ":")` instead of the default separators.**

Direction from Niek. Two independent changes to the same user message, done together
because both touch `_build_messages` right after D40 landed:

- *Question first.* The statements payload is the large, mostly-fixed part of the user
  turn; the question is a few words that used to trail dozens or hundreds of statements.
  Putting it first means the model's next token after the instruction it most needs — what
  to actually answer — isn't preceded by everything else it has to hold in mind first.
  This trades away prefix-cache reuse across questions against the same statement set (the
  varying part, the question, is now the prefix instead of the suffix, so an inference
  server that caches a shared prompt prefix — D2's caching is about `load_statements()`,
  not this — gets no reuse across two different questions); no such caching is currently
  configured on the Ollama side, so there is nothing to lose today.
- *Compact JSON.* `json.dumps(..., separators=(",", ":"))` drops the default `", "` and
  `": "` spacing, shrinking the payload by roughly one byte per field and value — the same
  token-cost motivation as D36/D40, applied to whitespace instead of structure. The default
  `json.dumps` here never emitted actual newlines (no `indent=` was ever passed — D40's
  base64 removal didn't change that), so this is a minification pass on top of D40, not a
  fix for a real newline that existed.

*Cost:* none identified for the compact separators. For question-first: if prefix caching
is ever added on the inference side (D40's own *Cost* note already flagged the base64→plain
move as relevant to that), this ordering is the one to revisit — it optimizes for the
single-question case at the expense of the repeated-question-same-corpus case, and D2 never
measured either against real latency numbers.
---

## D42 — 2026-09-19 — Accepted
**Deletion is one function over the statements file: resolve one person, replace every spelling in every text field, return a receipt. Refines D3 and D19.**

`statement_extraction/src/app/deletion.py` takes the statements and a name and returns the redacted
statements and a receipt. It reads nothing else and keeps nothing: the deleted name is not written
anywhere, and the file keeps only the placeholder. The person is resolved from the statements alone
(D19): the actor and `agreed_by` names, plus "First Last" pairs in the text whose first name belongs
to a known actor, which is how a mentioned-only person such as Nadia Öberg turns up. Spellings that
differ only by accents are one person (`Henrik Sørensen` and `Henrik Sorensen`). An exact full name
wins outright; a bare first name picks the person with the most statements. A speaker the file only
labels (`Guest 1`, `Them`) is never a person.

What is replaced, in this order: the full name (either order), an email of the form
`first.last@`, `f.last@` or `last.first@`, then the last name and the first name on their own, but
only when nobody else in the file shares that name. Otherwise the bare name is left, and the
receipt says who shares it. Every string field is swept except ids, dates, `position`,
`speech_act`, `handling` and `doc_type`, so a field added later is covered by default. The
placeholder is `[former RELEX employee]`, `[former customer employee]` or
`[former partner employee]` from the organisation the file states for that person, and
`[former participant]` when it states none. Role and organisation stay, as D3 accepts.

Rejected:
- *The hard-coded cast in `statement_extraction/pipeline/registry.py`.* It has no Nadia Öberg, so a
  bare "Nadia" would look safe to redact, and it is a second list of names to keep in step with
  the archive.
- *Always redacting a bare first name.* Deleting Nadia Haddad would take the one mention of Nadia
  Öberg with it.
- *Never redacting a bare first name.* "Kwame" stays in 13 places after Kwame Boateng asked to go.
- *Sweeping only `actor`, `agreed_by`, `verbatim_span` and `claim`.* A field added later would keep
  the name.

*Cost:* deleting Nadia Haddad leaves "Nadia" on its own in about 23 places, because it could also
mean Nadia Öberg; the receipt says so, and a reader can still guess. Email forms are patterns, so
an unusual address survives. Phone numbers are not covered, because nothing in a statement ties a
number to a person; the receipt says how many statements contain one. A capitalised pair beginning
with a known first name is taken for a person, which could add a false one and stop a bare first
name from being redacted; on this archive the only extra person it finds is Nadia Öberg. Nothing
calls the function yet: the backend mounts the file read-only and extraction is the only writer, so
how the demo triggers a deletion is still to be decided.

---

## D43 — 2026-09-19 — Accepted
**Deletion is a command in `statement_extraction` that rewrites the statements file in place and prints the receipt. Extends D42.**

`uv run python -m src.app.delete "Kwame Boateng" [--dry-run]`, next to `extract.py`. It reads and
writes `STATEMENTS_FILE_PATH`, the file extraction writes, and reuses extraction's whole-or-nothing
writer, so a crash cannot leave a half-written record. In compose the extraction container is the
only one with the volume mounted read-write, so the file still has exactly one writer:
`docker compose run --rm --no-deps statement-extraction uv run --frozen python -m src.app.delete "<name>"`.
The receipt is printed to the terminal as JSON and stored nowhere, since it names the person
(D42). Exit 0 means the file was rewritten (or a dry run printed a receipt), 1 means nobody
matched and the file was left untouched, 2 means there is no file. If a `documents/` folder from
an interrupted extraction run sits next to the file, the command says it still holds the name.

Rejected:
- *Keeping a copy of the file from before the deletion, so a wrong name can be undone.* The copy
  is a second place the person survives (rule 4). A wrong name is undone by re-extracting, which
  D3 already says not to do after a deletion.
- *Writing the receipt to a log next to the file.* It would keep the deleted name in an
  audit trail, which undoes the deletion.
- *Making the backend do it.* It mounts the file read-only and holds only the answering path.
  Where the demo's trigger lives is still an open team decision (`docs/deletion.md`); this command
  is what any trigger would call, so it does not pre-empt that choice.
- *Refusing a bare first name that could mean two people.* D42 already resolves it, to the person
  with the most statements, and the receipt says who else it could have been. A refusal would make
  "delete Nadia" unrunnable.
- *Removing the leftover `documents/` folder from here.* It is extraction's scratch space, not
  ours to delete; the command warns and leaves the call to whoever owns extraction.

*Cost:* the rewrite cannot be undone, which is the point. The backend caches the file by path, so
its answers keep the old names until it restarts; until that is settled a deletion is complete on
disk but not yet in what a judge sees. The receipt exists only on the screen of whoever ran the
command, so the demo has to show it there or the frontend has to be given it (docs/deletion.md,
step 5). A second run of the same name finds nobody and exits 1, which is honest but reads as an
error in a script.

---

## D44 — 2026-09-19 — Accepted
**The backend reads the statements file on every request and caches nothing. Closes the reload question D43 left open.**

`load_statements` in `backend/src/app/statements.py` used `lru_cache`, so a running backend kept
the file it first read. A deletion (D42, D43) rewrites the file on disk, and the backend went on
answering with the old names until it restarted. It now reads and validates the file on each
request. That costs 28 ms for 1,116 statements (1 MB), against seconds for the model call, and every
request already re-serialises the whole file into the prompt (D2). The read is also explicitly
UTF-8: the default on Windows is cp1252, which cannot decode "Öberg" or "Sørensen", so a local
backend could not load a real file. The container was not affected. Checked against the running
app: ask, delete Marco Rossi with the D43 command, ask again, with no restart. The name is gone,
the placeholder is there, and all five citations still resolve.

Rejected:
- *Restarting the backend after each deletion* (`docker compose up --no-deps backend`, D12). No
  code, but a manual step that fails silently: forget it and the answer still names the person,
  which looks like the deletion did not work, on the slice the judges test directly. A trigger in
  the UI would also need the container runtime's socket.
- *A cache keyed on the file's modification time and size.* It keeps the cache, and a cache is a
  copy of the derived artifact that deletion would have to reach (rule 4). The invalidation logic
  is code to debug under time pressure, to save a parse that is cheaper than the rest of the request.
- *A reload endpoint that the deletion command calls.* A new call between services, and state that
  has to be kept in step with the file.

*Cost:* each request pays the parse, about 28 ms per MB, which grows with the file; at ten times the
statements it is still small next to the model call, and D2 already sets the ceiling where this
design stops working. A request already running when the file is rewritten finishes with the old
names, and the next one has the new. A file that is not valid now fails the request instead of
serving an older copy, which is intended, and cannot happen from a half-written file because both
extraction and deletion replace the file whole. This replaces the last cost line of D43, that the
backend keeps the old names until it restarts.

---

## D45 — 2026-09-19 — Accepted, supersedes part of D42

**Deletion is rebased onto the regrouped, claim-only statements file (D36/D37): it takes the
`documents` array instead of a flat statement list, sweeps each document's own `people` and
`summary`, and recognises an unnamed speaker by the shape of the name now that the `label`
field is gone.**

This branch was written against the pre-D36 file — a flat `statements` array whose entries
carried `location`, `verbatim_span`, `agreed_by` and `actor.role`. While it sat unmerged,
`main` regrouped the file under its documents (D36) and cut a statement down to
`claim`/`actor`/`speech_act`/`statement_date` (D37). Rebasing onto that is not a textual
merge: only `backend/src/app/statements.py` and this log actually conflicted, and the
deletion code would have rebased *clean and silently wrong* — `delete.py` reads
`["statements"]`, which no longer exists, and `delete_person` would have walked a list of
document blocks looking for `actor` fields that live one level down.

Three things the new shape changes, and what was decided about each:

- **The unit of work is a document block, not a statement.** `delete_person(documents, ...)`
  takes and returns the `documents` array as stored. Rejected: *keeping the flat signature
  and having the command flatten and re-group around it.* Re-grouping means reconstructing
  which statement belonged to which document from a derived id, which is exactly the kind of
  cleverness that costs an hour at 2am — and the document block is what the file actually is.
- **`people` and `summary` are swept like any other text.** They are new, they hold names
  (`people` is a list of them), and they live on the document, not the statement. Leaving
  them would have left a deleted person's name in the file in 45 places — working agreement
  rule 3, and rule 4's "each derived artifact is a new place a deleted person survives"
  applied to new *fields* rather than a new file. `statements_changed` in the receipt still
  counts statements only, because that is the number a reader checks against the file; a
  header changing is not a statement changing.
- **An unnamed speaker is recognised by shape.** `output._actor` (D37) folds a transcript's
  `label` into `actor.name`, so "Guest 1", "Them" and "Unknown Speaker" now arrive looking
  like ordinary names — and "Guest 1" has two words, which is all `_find_people` used to
  require. Without this, deleting "Guest 1" would have looked like a real deletion and the
  receipt would have offered non-people as candidates. Rejected: *asking extraction to keep
  the `label` field.* That reverses a decision made on the project owner's explicit
  instruction (D37) to fix a problem that belongs to the consumer of the file, and the
  labels are a closed, known set — `documents.Unit` documents them.

`agreed_by` is still read if a statement carries it, so a file written before D37 resolves
the same people it always did; nothing writes it any more.

**Verified, not assumed:** the real extraction was run over the real 45-document corpus with a
scripted model, producing 1,596 statements in the new shape, and Kwame Boateng, Nadia and
Henrik Sorensen were deleted from it — no part of a deleted name survives anywhere including
the headers, the envelope keeps its shape, and the result still loads in the backend's own
`StatementsFile` model. Numbers and the two things that run does *not* prove are in
[deletion.md](deletion.md).

*Cost:* D42's description of what is swept is now wrong in its details — it names
`verbatim_span` and `doc_type`, which no longer exist. It is left as written, per this log's
append-only rule; this entry is the correction. The deeper cost is D37's, not this entry's:
the verbatim span was the one field deletion could point a judge at to prove a redaction
happened in real quoted text, and the claim is a paraphrase. Deletion still reaches every
place a name sits, but "show me the redacted quote" is no longer a thing the file can answer.

---

## D46 — 2026-09-19 — Accepted, supersedes the "making the backend do it" rejection in D43 and amends D12

**The deletion code lives in the backend service, and the backend mounts the statements
volume read-write. Answers Q4, against its own leaning.**

Direction from David: deletion has to be part of the backend container, because the
extraction container is not running when a judge asks for one. That is the fact Q4's
option A missed. D12 made extraction a job: it writes the file, exits 0, and is gone.
Reaching its code afterwards means `docker compose run`, a new container from an image
that has to still be on the VM, driven from a terminal — there is no path from the page to
any of it. Q4's option A (a fourth service built from the extraction image) fixes that by
keeping a server alive whose only job is deletion; the backend is already that server, on
the compose network, with the volume mounted and a healthcheck the frontend waits on.

What moved, whole, no copy left behind: `deletion.py`, `delete.py` and their 25 tests, from
`statement_extraction` to `backend`. Q4's objection to option B was "the deletion code has
to be copied into the backend or shared between two packages, so there are two copies to
keep the same" — that objection assumed extraction still needed it, and it does not.
Extraction now imports nothing from deletion and deletion imports nothing from extraction;
its one dependency on extraction was `extract._write_json`, which is re-stated as
`statements.write_statements` (six lines, deliberately written twice rather than shared
across two workspace packages for a temporary-file-and-rename).

The file still has one writer at a time, which is what D12's clause is for. Extraction
creates it and exits; compose starts the backend only after that job completes, so the two
never hold the file at once. Two deletions arriving together are serialised by a
process-wide lock around read-redact-write in `delete_from_file`, and every write is
whole-or-nothing, so the answering path — which re-reads the file on every request (D44) —
sees the file from before a deletion or after it, never half of each.

CLAUDE.md rule 2 is untouched: `/query` still reads the statements file and nothing else.
Deletion is a different endpoint on the same service; it calls no model, reads no source
document, and cannot be reached from the answering path.

The command's default path changed with it, from `./statements.json` to
`config.statements_file_path()` — the same default the answering path uses, the bundled
mock file. Rejected: *keeping a separate default for the command.* Two defaults means a
local run can rewrite a file the backend never reads, which looks exactly like a deletion
that failed. The cost is that `uv run python -m src.app.delete "…"` with no
`STATEMENTS_FILE_PATH` set now redacts the committed mock fixture; it is under git, and the
container always sets the variable.

Also rejected: *a fourth compose service from the extraction image* (Q4's leaning) — a
service, a healthcheck and a deploy step to get wrong on Saturday evening, `fastapi` back
into a package that stopped being a server at D12, and a second container mounting the
volume read-write for no gain over a container that already exists. And *running the
command by hand when a judge names someone* (Q4's option C) — the judges use the app
themselves, so it fails the definition of done; it remains the fallback if the endpoint
breaks.

*Cost:* the backend process can now write `/data`. Before, the read-only mount made "the
answering path cannot damage the record" a property of the deployment; now it is a property
of the code, and a bug in the answering path could in principle corrupt the file the demo
depends on. `architecture.md`'s line about extraction being a FastAPI service "so that …
the deletion operation can be triggered without redeploying anything" is now wrong twice
over and is corrected there. Q5 is untouched and gets worse to explain: `docker compose up`
still re-runs extraction, which still puts a deleted person back, and that is now a
different service's behaviour undoing this one's.

---

## D47 — 2026-09-19 — Accepted, closes Q4's second half and step 5 of docs/deletion.md

**The page deletes through `POST /delete` on the backend, in one step, and shows a
plain-language confirmation that names who was resolved and who was deliberately left —
not the receipt JSON.**

The header has a "Delete a person" button on every screen. It opens a dialog: a name, a
line saying what is about to happen and that it cannot be undone, and one button. The
backend runs the deletion and returns the receipt (D42) as a typed response; the page turns
it into two or three sentences and drops it. "Done" clears the answer currently on screen,
because it was written before the deletion and can still name the person.

Direction from David: one step and a confirmation, no dry-run preview. Rejected with it:
*preview-then-confirm*, which would resolve the person first and let a judge see who they
are about to remove before it is irreversible — a click and a second call for a safety net
against a typo, and the same sentences get shown either way.

What the confirmation may not drop, and does not: the name deletion resolved the request
to, and anyone it deliberately left. The archive plants two people sharing a first name
(corpus.md, D19), so after deleting "Nadia" a judge who asks around the edges finds "Nadia"
still in the record — and only this sentence distinguishes an identity we resolved and a
bystander we kept from a redaction that missed half a person. The rubric does not ask for a
receipt; the trap is what asks for it.

Rejected:
- *The receipt as JSON in the page.* It reads as debug output, and the part that matters —
  who was left, and why — is legible only to someone who already knows the shape.
- *A success toast with no names.* Cheapest, and it throws away the answer to the one
  question the judges are planted to ask.
- *Storing the receipt so it can be shown again.* It names the person; keeping it anywhere
  undoes the deletion (D42, D43). It lives in `st.session_state` for the life of the dialog
  and is cleared when the dialog closes.
- *A 404 when nobody matches.* `deleted: null` with the file untouched is an answer, not an
  error, and the page says "no one called X is in the record. They may already be deleted."
  A missing statements file is a 503, because that one really is broken.

*Cost:* anyone who opens the URL can permanently delete anybody, on the instance the next
judge will use, with no undo and no confirmation beyond one button — a judge who deletes
Kwame Boateng early leaves the next one without him for the provenance questions. Q4 raised
that and it is still unanswered; the only reset is a re-extraction, which is slow and runs
into Q5. A typo that happens to resolve to a real person deletes that person. And the
confirmation is a page element, not a record: once the dialog closes, "show me that again"
is not something the system can do, which is deliberate.

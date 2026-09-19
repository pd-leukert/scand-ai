# Second-pass reconciliation layer

## Context

The currency slice is 20% of the rubric and we currently score zero on it. D4 put currency
out of scope for the MVP and D16 confirmed it while naming the successor: *"a second LLM
pass over the aggregated statements that groups them by topic, writes explicit
supersedes/contradicts links, and assigns a status."* The MVP has since landed — extraction
runs (D28/D30), the answering path works (D21/D27) — so the condition D16 set is met.

The rubric names two distinct failures, not one: **stale** (true when written, reversed
later) and **never-true** (wrong when recorded). A date sort cannot tell them apart, and
the brief says so explicitly. Three of the nine practice questions are currency questions;
P9 (the "nightly article extract completed, no errors" reports) is unanswerable without the
never-true distinction, and P6 (bakery in or out of the fresh workstream, changing across
transcripts 17/19/20) is the stale set piece.

This builds that pass, inside the existing `statement-extraction` job, running strictly
after the first pass finishes. It produces a second derived artifact, `reconciled.json`,
and the answering path reads that instead of `statements.json`.

**This supersedes D4 and D16 and requires rewording CLAUDE.md rule 5**, which currently
forbids the feature outright.

## Settled design decisions

| Question | Choice |
|---|---|
| Output | A **second file**, `reconciled.json`, **fat / self-contained** — full statement records nested inside each topic. The backend reads only this file. |
| Grouping | **Two stages**: (A) per-statement topic tagging in batches with a running vocabulary threaded forward; (B) one reconciliation call per topic. |
| Failure | **Hard fail.** Any error exits non-zero and writes nothing, so the compose gate holds the backend. |
| Group content | Links + statuses + **a one-sentence summary carrying the statement ids it rests on**. |
| Statuses | **Five, all link-derived**: `current`, `stale`, `never-true`, `disputed`, `unresolved`. |
| Problems | **One list, read by both** the answering model and the operator (printed at end of run). |
| Scope | **Full path**: extraction container + backend + frontend pill. |

---

## 1. `statement_extraction/src/app/reconcile.py` (new)

Module docstring, house style:

> *Second pass: group the first pass's statements by topic, then reconcile each topic.
> Nothing here writes a new quote. Every relation, status, receipt and problem names a
> statement id the first pass already produced; anything else is dropped. See D42.*

**The model never sees a statement id.** Both stages render statements under local labels
`S1 … Sn` and map back in code. `transcripts/07_2024-11-12_ordering-logic-design#12` is not
something a 0.6b model copies reliably, and every corruption would be a silently dropped
link. This is the mechanism that makes rule 1 true by construction on this side, the same
way `_resolve_citations` does on the answering side.

### Constants

```python
RELATIONS = ["supersedes", "corrects", "conflicts-with", "answers"]
STATUSES = ["current", "stale", "never-true", "disputed", "unresolved"]
PROBLEM_KINDS = ["reversal", "never-true", "conflict", "unanswered"]
UNTAGGED = "untagged"
```

### Functions

```python
class ReconcileError(RuntimeError):
    """The pass produced something that does not hold together. The job exits 1."""


def tag_topics(records, chat, batch, vocabulary_shown) -> tuple[dict[str, str], Counter[str]]
```
Batches records in first-pass order. Shows `Topics already in use: …` — the
`vocabulary_shown` most-used topics, ordered by use then name, so the list is stable and
bounded. Normalises each returned topic to a kebab slug
(`" ".join(t.split()).casefold().replace(" ", "-")`), so `Shelf Life Coverage` merges onto
`shelf-life-coverage`. Untagged statements fall to `UNTAGGED`.

```python
def group(records, topics, cap) -> list[tuple[str, list[dict]]]
```
Topics largest first, statements oldest first. A topic over `cap` is cut into consecutive
date-ordered chunks (`"bakery-workstream-scope (1 of 2)"`) because one call has to hold it.

```python
def chronological(record) -> tuple:
    return (record["stated_on"], record["doc_id"], *when(record))
```
Reuse `extraction._when` — **rename it to `when`** (three-line change: the `def`, its caller
in `link_agreements`, the import here). It is the only place that knows an email thread is
filed newest-first, and now two modules need it.

```python
def reconcile_topic(topic, statements, chat) -> tuple[dict, Counter[str]]
def statuses_from(relations, statements) -> dict[str, str]
def problems_for(topic, model_problems, relations, statuses) -> list[dict]
def reconcile(records, chat, *, batch, vocabulary_shown, topic_cap,
              max_untagged, max_topics, progress=print) -> tuple[list, list, Counter[str]]
def _check(topics, problems, records) -> None
```

**`statuses_from` is where currency is actually decided — by links only, never by dates.**
Precedence, highest first; `never-true` deliberately beats `stale`, because reporting a
record that was never true as merely old is one of the three failure modes the brief names:

| what the surviving links say about B | B's status |
|---|---|
| some A `corrects` B | `never-true` |
| some A `supersedes` B | `stale` |
| some A `conflicts-with` B (either direction) | `disputed` |
| B is `proposal`/`question`, nothing `answers` B, `agreed_by` empty | `unresolved` |
| otherwise | `current` |

`current` is the default and the only status needing no relation. The model *proposes*
statuses; code re-derives them from links that survived validation and **the code wins**,
counted as a drop. That is what "a status is only valid if justified by a named relation to
a named statement id" means mechanically.

`reconcile` is sequential — one topic per call, independent contexts, no shared state.
Concurrency later is a `ThreadPoolExecutor` around the loop body and nothing else, but
Ollama serves one request at a time unless `OLLAMA_NUM_PARALLEL` is set, and a deterministic
log is worth more this weekend.

---

## 2. The two Ollama schemas

Same style as `SCHEMA` / `LINK_SCHEMA` in [extraction.py](../../statement_extraction/src/app/extraction.py#L10-L39).
Every `statement` / `from` / `to` the model writes is a local label, not an id. The enums are
a hint, not a guarantee — `extract_document` already re-checks `item["act"] not in ACTS`
despite the schema, and this code re-checks the same way.

```python
TOPIC_SCHEMA = {
    "type": "object",
    "properties": {
        "tags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "topic": {"type": "string"},
                },
                "required": ["statement", "topic"],
            },
        }
    },
    "required": ["tags"],
}

RECONCILE_SCHEMA = {
    "type": "object",
    "properties": {
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "kind": {"type": "string", "enum": RELATIONS},
                },
                "required": ["from", "to", "kind"],
            },
        },
        "statuses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "status": {"type": "string", "enum": STATUSES},
                },
                "required": ["statement", "status"],
            },
        },
        "summary": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "statements": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text", "statements"],
        },
        "problems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": PROBLEM_KINDS},
                    "statements": {"type": "array", "items": {"type": "string"}},
                    "note": {"type": "string"},
                },
                "required": ["kind", "statements", "note"],
            },
        },
    },
    "required": ["relations", "statuses", "summary", "problems"],
}
```

---

## 3. Prompts

Voice and line-continuation style match `SYSTEM_PROMPT` / `LINK_PROMPT`.

### `TOPIC_PROMPT` (stage A)

```
You sort statements from a project record into topics. A topic is one thread of subject
matter that runs through the project: a field, a workstream, a date, a decision people kept
coming back to.

You are given statements, each with a label, a date, who said it and what it says. You are
also given the topics already in use in this run.

For every statement, return:
- statement: the label exactly as shown, e.g. S3. Never write a label you were not given.
- topic: a short kebab-case tag naming the subject, two to four words, lower case, letters,
digits and hyphens only, e.g. "op-id-field-exclusion" or "bakery-workstream-scope".

Reuse a topic from the list you were given whenever it fits. Only invent one when no topic
in that list covers the statement. Two spellings of the same subject are worse than one
imperfect topic. Name the subject, never the speech act and never the document:
"shelf-life-data-coverage", not "proposal" and not "email-07".

Give exactly one entry for each statement you were given. Do not repeat a label. Do not use
"untagged". Use only the text you are given.
```

### `RECONCILE_PROMPT` (stage B)

```
You read every statement in a project record about one topic, oldest first, and write down
how they bear on each other. You never write a new fact: everything you return points at
the statements you were given, by their labels.

Return:

- relations. from and to are labels from this topic.
  - supersedes: the statement in from replaces what to said. Later words settled it
differently.
  - corrects: from says to was wrong when it was recorded. Not that things changed since —
that the record was never right.
  - conflicts-with: from and to cannot both be true, and nothing here settles which holds.
  - answers: from answers the proposal or question in to, by accepting it, refusing it, or
settling it either way.
  Write only a relation the words show. Most statements have none. Never link a statement
to itself, and never link two statements that only repeat each other.

- statuses, one for each statement.
  - current: nothing here supersedes it, corrects it or contradicts it.
  - stale: a later statement supersedes it.
  - never-true: another statement says it was wrong when it was recorded.
  - disputed: it conflicts with another statement and nothing settles which is right.
  - unresolved: it is a proposal or a question and nothing here answers it.
  A status other than current is allowed only if you also wrote the relation it rests on.
Never decide a status from dates. Being old is not being stale, and being recent is not
being right.

- summary: one plain sentence saying where this topic stands, and statements: the labels
that sentence rests on. Say it in your own words. Do not quote the record — the labels are
the receipt, the sentence is not.

- problems: one entry for anything a reader of this record would get wrong.
  - reversal: a decision was changed later and the earlier statement still reads as current.
  - never-true: a statement was wrong when it was recorded.
  - conflict: two statements disagree and nothing settles it.
  - unanswered: something was proposed or asked and nobody ever answered it.
  Each entry names the labels involved and one plain sentence saying what a reader would get
wrong. Do not quote the record.

Use only the statements you are given. Never write a label that is not in the list.
```

---

## 4. Shape of `reconciled.json`

**One statement belongs to exactly one topic**, so the file is `statements.json` plus a
wrapper, not a multiple of it. **Relations live on the topic, not duplicated onto each
statement** — one entry per link instead of two, which matters under D2.

```json
{
  "generated_on": "2026-09-19",
  "statement_count": 1184,
  "topic_count": 41,
  "relation_count": 62,
  "problem_count": 14,
  "topics": [
    {
      "topic": "nightly-extract-health",
      "summary": {
        "text": "Three weekly updates reported the nightly article extract as completed with no errors, and a later hypercare statement says the article master was not loading at the time.",
        "statements": ["reports/01_weekly-status-thread#12", "transcripts/11_2025-03-18_hypercare-review#7"]
      },
      "relations": [
        { "from": "transcripts/11_2025-03-18_hypercare-review#7",
          "to": "reports/01_weekly-status-thread#12",
          "kind": "corrects" }
      ],
      "statements": [
        {
          "id": "reports/01_weekly-status-thread#12",
          "document_id": "reports/01_weekly-status-thread",
          "doc_type": "report",
          "location": { "page": null, "line_start": 214, "line_end": 214, "position": "message 9 of 18" },
          "verbatim_span": "Nightly article extract completed, no errors.",
          "claim": "The weekly update reported the nightly article extract completed with no errors.",
          "speech_act": "report",
          "handling": "none",
          "actor": { "name": "Ana Duarte", "label": null, "organization": "RELEX", "role": "Not stated" },
          "agreed_by": [],
          "statement_date": "2025-09-05",
          "document_date": "2026-04-17",
          "status": "never-true"
        }
      ]
    }
  ],
  "problems": [
    {
      "kind": "never-true",
      "topic": "nightly-extract-health",
      "statements": ["reports/01_weekly-status-thread#12", "transcripts/11_2025-03-18_hypercare-review#7"],
      "note": "The weekly update reporting a clean nightly extract was not right when it was written; a hypercare statement says the article master was not loading at the time."
    }
  ]
}
```

Written by a new `to_reconciled(topics, problems, generated_on)` in
[output.py](../../statement_extraction/src/app/output.py), nesting
`to_statement(record) | {"status": statuses[record["id"]]}`. **`to_statement` is unchanged** —
one function still owns the statement's public shape.

---

## 5. Validation

Every drop is counted in a `Counter[str]`, printed per topic and summed for the run, exactly
like `extract_document`'s `dropped`. Nothing is retried; nothing is repaired in place except
slug normalisation.

**Stage A** — drop a tag whose label was not shown in this batch; whose topic is not a slug
after normalisation or is over 40 chars; which uses the reserved `untagged`; or which
repeats a label (first wins). Statements the model forgot fall to `untagged`.

**Stage B** — drop a relation naming a label not in this topic, pointing at itself,
duplicating another, or carrying a kind outside `RELATIONS`. Drop a status for a label not
in this topic or outside `STATUSES`; where the model's status disagrees with what surviving
relations give, **code wins**. Drop a summary receipt naming a label not in this topic, and
drop the summary whole if it ends with no receipts or empty text. Drop a problem naming a
label not in this topic, or whose kind no surviving relation supports. Append a
**code-generated** problem entry for any flagged statement the model forgot, from a template
so it cannot invent: `f"{late} supersedes {early}; the record still reads as if {early} stands."`

**Two prose guards.** The topic summary and the problem note are the only model-written prose
in the artifact. Drop either outright if it contains a quotation character, or if a note runs
over 300 characters. A model-written sentence in quotes is the one thing a judge could mistake
for a citation, so it is dropped rather than shown — same reflex as `find_span`.

**One date guard, and it creates nothing.** Drop a `supersedes` link whose `from` is strictly
earlier in `stated_on` than its `to`. This rejects a model error; it never produces a status.
It is deliberately **not** applied to `corrects`, the relation that produces `never-true`, so
that relation stays entirely date-free. Same-day links pass. D42 names this explicitly so
nobody later reads it as rule 5 being bent.

**Two gates against the failure that looks like success** — a grouping so fragmented that no
topic holds two statements, producing zero links and labelling the whole corpus `current`.
Both raise `ReconcileError`:
- more than `RECONCILE_MAX_UNTAGGED` (0.1) of statements untagged;
- more topics than `RECONCILE_MAX_TOPICS` (0.35) of the statement count.

**`_check`, the whole-artifact gate before anything is written**, independent of the
per-response filters — because a bug in those is exactly what those would not catch. Raises
`ReconcileError` unless: every input statement id appears in exactly one topic and every
output id is an input id; every relation end is inside its own topic; every summary receipt
and problem id resolves; every status is one of the five; every non-`current` statement is
named in at least one problem; and the four counts match what is actually in the file.

---

## 6. `extract.py` — wiring phase 2

New config reads, matching the existing block at [extract.py:39-55](../../statement_extraction/src/app/extract.py#L39-L55):

```python
    reconcile_model = os.environ.get("RECONCILE_LLM_MODEL") or model
    reconcile_num_ctx = int(os.environ.get("RECONCILE_NUM_CTX", "8192"))
    reconcile_batch = int(os.environ.get("RECONCILE_BATCH_STATEMENTS", "20"))
    reconcile_timeout = float(os.environ.get("RECONCILE_TIMEOUT", "600"))
    topic_cap = int(os.environ.get("RECONCILE_TOPIC_MAX", "40"))
    vocabulary_shown = int(os.environ.get("RECONCILE_VOCABULARY_SHOWN", "40"))
    max_untagged = float(os.environ.get("RECONCILE_MAX_UNTAGGED", "0.1"))
    max_topics = float(os.environ.get("RECONCILE_MAX_TOPICS", "0.35"))
    reconciled_out = Path(os.environ.get("RECONCILED_FILE_PATH", "reconciled.json"))
```

Control flow after the existing `os.replace(tmp, out)`:

1. **Move the `empty` check up**, so a run with a silent document returns 1 *before* phase 2 —
   a broken record must not be reconciled.
2. Open a second `httpx.Client` with `reconcile_timeout`, build `chat` via the existing
   `_ollama_chat(client, reconcile_model, reconcile_num_ctx)`, and call `reconcile(...)` inside
   a `try`. Catch `(httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ReconcileError)`,
   print to stderr, `return 1`. Hard fail: the compose gate holds the backend rather than let it
   answer from a half-reconciled record, and any earlier `reconciled.json` is left alone.
3. Atomic write — same `.tmp` + `os.replace`, same `ensure_ascii=False, indent=2`.
4. Print, in order: the drop Counter, the per-topic line, the **problems list**, and a
   **size line**. The size line is how D2's unmeasured ceiling finally gets measured:

```python
def _size_report(statements_path: Path, reconciled_path: Path) -> str:
    """D2's ceiling is unmeasured until something measures it. The whole reconciled file goes
    into the answering context, base64-encoded (D21), so report what that actually costs."""
```
→ `statements.json 812 kB, reconciled.json 947 kB (+16%), about 315k tokens once base64-encoded into the answering context.`

Exit codes keep the existing convention: **2** for unconfigured (no model resolvable),
**1** for a failed run, **0** for success.

---

## 7. Backend

### [statements.py](../../backend/src/app/statements.py)

Add `Status`, `RelationKind`, `ProblemKind` literals. `Statement` gains
`status: Status = "current"` (the default keeps an older file loadable). New `Relation`
(with `from`/`to` aliases via `populate_by_name`), `Summary`, `Topic`, `Problem`,
`ReconciledFile`. Replace `StatementsFile` / `load_statements` with:

```python
@dataclass(frozen=True)
class Record:
    """What the answering path holds: topics for the context, statements indexed by id for
    citation resolution, and for each non-current statement the ids that justify its status."""
    topics: list[Topic]
    problems: list[Problem]
    statements: dict[str, Statement]
    receipts: dict[str, list[str]]


@lru_cache
def load_record(path: str) -> Record: ...
```

`receipts[id]` is built at load time by walking every topic's relations: for `stale`, the ids
that supersede it; for `never-true`, the ids that correct it; for `disputed`, the ids it
conflicts with. This is what lets a citation carry its own justification.

The loader stays `@lru_cache`d by path. Note in the docstring that **deletion, when built,
must call `load_record.cache_clear()`** or deleted names keep answering out of a warm process.

### [schemas.py](../../backend/src/app/schemas.py)

`Citation` gains `status: Status` and `status_receipts: list[str] = []`. Both are copied from
our own loaded file — **the answering model never asserts a statement's currency, it reads it.**
Same trust boundary D21 draws for citations.

### [llm_client.py](../../backend/src/app/llm_client.py)

- `load_statements(settings.statements_file)` → `load_record(settings.reconciled_file)` at both
  call sites ([:159](../../backend/src/app/llm_client.py#L159), [:185](../../backend/src/app/llm_client.py#L185));
  `statements` becomes `record.statements` wherever citations resolve.
- `_build_messages` encodes `{"topics": [...], "problems": [...]}`, base64 exactly as before —
  **D21's transport and trust boundary are untouched.**
- `_resolve_citations` adds `status=statement.status` and
  `status_receipts=record.receipts.get(statement.id, [])`.
- `SYSTEM_PROMPT`: **rule 4 must be replaced.** It currently says *"Do not decide which one is
  current — you have no way to know that"*, which is now false. New rules 4–7 tell the model to
  use the status, to report a stale or never-true statement as what the record *once* said while
  naming and citing what superseded or corrected it, never to judge currency itself, to report a
  `disputed` pair as a conflict citing both sides, and to surface a `PROBLEMS` entry when the
  question touches one. Existing citation rules 5/6 shift down to 8/9.

### [config.py](../../backend/src/app/config.py)

`Settings.statements_file` → `reconciled_file`, read from `RECONCILED_FILE_PATH`, defaulting to
a new `backend/src/app/data/mock_reconciled.json` — the same statements wrapped in two topics,
one relation, one problem, so `DUMMY_LLM=true` still exercises the whole wire contract including
the new fields (D15 stands). `main.py` needs no change.

---

## 8. Frontend

Three small edits to [app.py](../../frontend/app.py), no logic moved into it — the status and the ids
that justify it are computed by the backend and only rendered here.

1. Four pill colour classes next to `.sc-pill` in `STYLE` ([:137](../../frontend/app.py#L137)), plus a
   `.sc-receipt` muted line.
2. A `STATUS_PILLS` map and `status_pill(status)` next to `location_label`
   ([:171](../../frontend/app.py#L171)). `current` gets **no pill** — a pill is a warning, and
   everything the record does not flag is current. Labels: `Superseded`, `Never true`,
   `Disputed`, `Never answered`.
3. In `render_source_row` ([:256](../../frontend/app.py#L256)), one line after the speech-act pill at
   [:281](../../frontend/app.py#L281); and inside the `if expanded:` block, under the quote, a
   `Because of <ids>` line from `citation["status_receipts"]`.

---

## 9. Compose, Dockerfiles, env

- `statement_extraction/Dockerfile` and `backend/Dockerfile`: `ENV RECONCILED_FILE_PATH=/data/reconciled.json`.
- `compose.yaml` → `ollama-pull`: add `RECONCILE_MODEL=${RECONCILE_LLM_MODEL:-${EXTRACTION_LLM_MODEL:-${LLM_MODEL:-qwen3:0.6b}}}`,
  a line in the resolved-config banner, and `&& ollama pull "$$RECONCILE_MODEL"`. **Without this
  a separately configured reconciliation model 404s in the middle of the longest job in the stack.**
- `compose.yaml` → `statement-extraction`: add the same `RECONCILE_LLM_MODEL` line, with a comment
  saying reconciliation is a reasoning pass over short contexts, not a copying task, and that it
  defaults to the extraction model which defaults to the answering one.
- `compose.yaml` → `backend`: add `RECONCILED_FILE_PATH=/data/reconciled.json`.
- The `statements:` volume comment changes to name both artifacts. `depends_on` is unchanged —
  the gate is already `service_completed_successfully` on the whole job, which now includes phase 2.

**No new Python dependency.** `json`, `re`, `os`, `Counter` and the existing `httpx` cover all of
it, so `statement_extraction/pyproject.toml` and `uv.lock` are untouched.

---

## 10. Docs — required, not optional

**`docs/decisions.md`** — append **D42**, dated 2026-09-19, `Accepted *(supersedes D4 and D16)*`,
and mark `## D4 … — Superseded by D42` and `## D16 … — Superseded by D42`. Bold decision, prose,
`Rejected:` list, `*Cost:*`. It must contain:

- **Rejected**: a date sort in any form (and an explicit note that the one date read is a guard
  rejecting a backwards `supersedes` link, which creates no status and is not applied to
  `corrects`); conflict-detection-only (D16's reason, re-weighed); one global reconciliation call;
  pairwise comparison of every statement; writing statuses back into `statements.json` (links and
  summaries have nowhere to live in a flat list, and a pass that rewrites its own input destroys
  the thing it was derived from); a thin id-referencing second file (the backend would join two
  files to answer one question).
- **Cost, four parts**:
  1. **Two derived artifacts, and deletion is not built yet.** This is exactly the condition D3
     named — *"no re-extraction after a deletion, and no second derived artifact. Both hold today.
     If either changes… this decision has to be revisited, because the name comes back."* One has
     now changed, deliberately, before deletion exists. Deletion must redact both files, and the
     second is strictly harder: a deleted name can appear in nested verbatim spans and actor fields
     **and in the topic summaries and problem notes, which are model-written prose**. Those
     summaries are literally what the rubric's deletion band calls *"any cached summaries"*. Plus
     `load_record` is `lru_cache`d and must be cleared.
  2. **D2's ceiling moved and the run now measures it.**
  3. **A missed link is a statement reported as `current`.** Untagged statements, chunked topics
     and links the model didn't see all fail the same, safe direction — but the signal is a floor,
     not a guarantee, and the honest limit must say so.
  4. **A third model-config chain** (`RECONCILE_LLM_MODEL` → `EXTRACTION_LLM_MODEL` → `LLM_MODEL`),
     with D25's half-set-configuration cost applying again.
- **Conditions this decision depends on**: that deletion is built against both files and both kinds
  of text as a single piece of work. If deletion ships touching only `statements.json`, the honest
  answer is to stop writing the summaries rather than claim a deletion we do not have.

**`CLAUDE.md` rule 5** — replace outright, since it currently forbids this feature:

> 5. **Currency is link-derived, never date-derived.** A statement is *stale* only because a named
>    later statement supersedes it, and *never-true* only because a named statement says it was
>    wrong when it was recorded — and the statement ids that justify the label travel with it all
>    the way to the citation (D42). Do not add a date heuristic, do not let the answering model
>    improvise a status, and do not let a statement be flagged by anything but a link to another
>    statement that exists. If the reconciliation pass did not label it, it is current, and
>    "current" means only that nothing we grouped with it contradicts it.

**`CLAUDE.md` rule 4** — add a sentence: as of D42 there are two derived artifacts, and in the
reconciliation a deleted person can survive in model-written prose as well as in a verbatim span.

**Also update**: `README.md` requirement-3 row and the "How it works" steps 2–3;
`docs/roadmap.md` (extension 1 becomes built; the **"No currency signal"** honest limit is
*rewritten, not deleted*, into "Our currency signal is a floor, not a guarantee"; add a new limit
naming the summaries as model-written prose and the hardest thing for deletion to redact; the MVP
"Out:" list drops currency/reconciliation/cached summaries); `docs/data-model.md` (a new "What the
reconciliation pass adds" section, and "What deletion has to touch" gains the second artifact);
`docs/architecture.md` (diagram box, part 2 and 3, and "What the MVP does not have" must stop
saying "no cross-document reconciliation, no cached summaries"); `docs/open-questions.md` Q1 (the
contradiction-alarm and drift-report options are no longer blocked); `statement_extraction/README.md`
and `backend/README.md` (env vars, two-pass description, hard-fail behaviour).

---

## 11. Tests

Same conventions as the existing suite: module-level string fixtures, `record(**overrides)`
helpers, fake `chat` closures recording what they were shown (`chat.seen`), full-sentence names,
`dict(counter)` compared literally. No mocking library.

**New `tests/test_topics.py`** — every statement gets exactly one topic; a topic already in use is
shown to the next batch; a differently-spelled topic normalises onto the one in use; a tag for a
label that was not shown is dropped; a non-slug topic is dropped; a statement tagged twice keeps
the first; a forgotten statement lands in untagged; the reserved `untagged` cannot come from the
model; the vocabulary shown is capped and ordered by use; **the model is never shown a real
statement id**.

**New `tests/test_reconcile.py`** — a `supersedes` link makes the earlier statement stale; a
`corrects` link makes it never-true; **never-true wins when a statement is both corrected and
superseded**; a conflict marks both disputed; an unanswered proposal is unresolved; an answered one
is not; an untouched statement stays current; relations outside the topic / to itself / running
backwards in time are dropped; **a correction written on the same day is kept**; a status no
relation justifies falls back to current; summary receipts that resolve to nothing are dropped and
a receipt-less summary is dropped whole; a summary that quotes the record is dropped; problems
outside the topic or unsupported by a relation are dropped; every flagged statement ends up in the
problems list; statements are shown oldest first across documents; **a thread is shown in the order
it was written, not the order it is filed**; an oversized topic is chunked; too many untagged
statements stop the pass; a topic-per-statement stops the pass.

**Extend `tests/test_output.py`** — the reconciled file nests every statement exactly once; a
reconciled statement is a statement plus its status; a topic with no surviving summary still
carries its statements.

**Extend `tests/test_extract_job.py`** — the existing `job` fixture gains
`monkeypatch.setenv("RECONCILED_FILE_PATH", …)` and a fake chat that dispatches on which system
prompt it was handed (the same shape the file already uses). Tests: a run that reconciles writes
both files and succeeds; a failed reconciliation writes no reconciled file; a failed reconciliation
leaves an earlier one alone; a document with no statements fails before anything is reconciled;
reconciliation falls back to the extraction model when none is named; the run reports what the
reconciled file costs in context (`capsys`).

The backend has no test suite today and this does not invent one. If wanted, the two cheapest are a
`ReconciledFile` round-trip over a fixture and `_resolve_citations` carrying `status` and
`status_receipts`.

---

## 12. Verification

1. `cd statement_extraction && uv run --frozen pytest` — the full suite, old and new.
2. `uv run --frozen ruff check .` and `ruff format --check .` (line-length 100, py312).
3. **Single-document smoke run**, fast and offline-ish:
   `EXTRACTION_LLM_MODEL=qwen3:0.6b uv run python -m src.app.extract emails/07` — inspect
   `reconciled.json` by hand: every statement present exactly once, every relation end real,
   no summary containing a quotation mark.
4. **Full run**: `docker compose up --build`. Watch the extraction job's tail for the per-topic
   lines, the problems list and **the size line** — that number is D2's answer and belongs in the
   demo. Confirm the backend does not start if phase 2 fails (`docker compose ps` shows the job
   exited non-zero and `backend` never created).
5. **End to end in the UI** at `http://localhost:8501`, against the planted set pieces:
   - *"Is bakery in or out of the fresh workstream?"* → must report the reversal across
     transcripts 17/19/20, cite both sides, and show a **Superseded** pill on the earlier one.
   - *"Did the nightly article extract run cleanly?"* (P9) → must **not** repeat the weekly
     updates as fact; the reports should carry **Never true**, with the correcting statement
     cited. This is the one question where a correct citation and a wrong conclusion score nothing.
   - *"Was the operator ID field removal agreed?"* (P3) → attribution unchanged, still correct.
   - A question the record is silent on → still "The record does not say."
   - Expand a flagged citation → the `Because of <ids>` receipt resolves to real statements.
6. `DUMMY_LLM=true` against `mock_reconciled.json` — the SSE wire format still carries `status`
   and `status_receipts`.

---

## 13. Known risks, ranked

1. **Stage A fragments on `qwen3:0.6b` and the pass becomes a silent no-op.** A model that coins a
   near-duplicate topic per batch gives topics of size one, zero links, and a file where everything
   is `current` — which looks exactly like a successful run. Mitigated by the running vocabulary,
   slug normalisation and the two hard gates; the gate thresholds (0.1 / 0.35) are guesses until
   this runs once on the real corpus.
2. **Deletion now has two files and one contains generated prose.** The biggest scoring risk in the
   change — the deletion slice is 20% and its top band names "cached summaries" explicitly. **If
   deletion runs short on time, drop the summaries from the artifact** and keep only relations,
   statuses and problems, which are ids and enums and therefore trivially redactable. That is a
   one-line change in `to_reconciled` and it should be taken rather than shipping a half-redacted
   summary.
3. **Stage B over-links** — a small model writing `supersedes` between every consecutive pair.
   Worse than D4: a current decision reported as stale is the same class of error as the brief's
   "clean summary that is wrong". Partly caught by the backwards-in-time and self-link guards, not
   caught when links run the right way and are simply wrong. If it shows in testing, print relation
   density per topic as a review flag — a hard density gate is tempting and probably wrong, since a
   genuinely contested topic is dense.
4. **Cross-document date ordering rests on `stated_on`**, which for a transcript is just the meeting
   date. Statements in one document compare equal and fall back to first-pass order; the
   backwards-in-time guard tolerates equality for exactly this reason.
5. **A stale `reconciled.json` can outlive a fresh `statements.json`** if phase 2 fails after phase 1
   succeeds. Compose holds the backend so judges never see it, but `--no-deps backend` would. Cheap
   guard: carry `statement_count` in both and log a mismatch at load.
6. **Run time** — roughly +100 model calls on top of the first pass, and the whole thing is the
   compose gate. Fine on the VM's GPU, slow on a CPU laptop. `RECONCILE_WORKERS` is where the fix
   goes, and Ollama needs `OLLAMA_NUM_PARALLEL` to serve it.
7. **The answering model may over-apply the status**, refusing to mention a stale statement at all
   when the right answer cites it *and* what superseded it. Prompt rule 4 says so, but it is one
   more instruction on a model that already has nine.
8. **Topic chunking loses links across the seam** — a supersession crossing the cut is invisible and
   fails to `current`, like everything else that is missed.

Two things this change surfaces but does not decide: whether `claim` should enter the answering
context (D28 flagged it as undecided surface area, and this is the moment to decide), and whether
the topic summaries should be shown in the UI — they are the cheapest material for the "brief
someone joining on Monday" initiative option and are already generated. Worth a line in Q1.

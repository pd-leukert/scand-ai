# LLM B and the reconciled file, in plain words

The pipeline runs two LLM passes over the archive, once, offline. **LLM A** reads each
document and writes down what was said (`statements.json`). **LLM B** — this page — reads
those statements and works out how they relate to each other, and writes `reconciled.json`.
The answering backend reads that one file and nothing else.

> Why a second pass at all? LLM A reads one document at a time, so it can never notice that
> a July email replaced a June status report. LLM B is the only place where statements from
> different documents are put next to each other. Everything about *staleness* comes from it.

## What LLM B does, in four steps

It runs inside the `statement-extraction` job, after LLM A has finished. Code:
[reconcile.py](../statement_extraction/src/app/reconcile.py).

1. **Group by topic.** The model reads the statements in batches and gives each one a topic
   name (`go-live-date`, `replenishment-pilot`, …). Each batch is shown the topics already in
   use, so names converge instead of forking. A statement it cannot place is `untagged`.
2. **Find the links, one topic at a time.** For each topic the model gets that topic's
   statements, oldest first, under labels `S1`, `S2`, … (never real ids — it cannot mistype
   one) and writes the **relations** it can see between them:

   | relation | means |
   |---|---|
   | `supersedes` | the later statement replaces an earlier one that *was true when said* |
   | `corrects` | the statement shows an earlier one was *wrong when it was recorded* |
   | `conflicts-with` | two statements disagree and nothing says which holds |
   | `answers` | the statement answers an earlier question or proposal |

   It also writes a one-sentence topic summary and a note for anything a reader could get
   wrong. Code throws away every relation that names a statement that does not exist.
3. **Code works out the status.** The model's own opinion of a status is discarded. Code
   derives it from the relations that survived, strongest first:

   | status | when |
   |---|---|
   | `never-true` | some statement `corrects` it |
   | `stale` | some statement `supersedes` it |
   | `disputed` | it is in a `conflicts-with` |
   | `unresolved` | it is a proposal or question that nothing `answers` and nobody accepted |
   | `current` | none of the above — i.e. *nothing we grouped with it contradicts it* |

   No dates are involved. A statement is `stale` only because a named later statement
   replaces it (CLAUDE.md rule 5).
4. **Check and write.** Gates refuse a run that looks like success but is not (everything in
   one topic, everything in a hundred topics, over half a topic flagged). A refused run
   writes nothing, so the backend never answers from a half-reconciled record.

## How to read `reconciled.json`

```jsonc
{
  "generated_on": "2026-09-19",
  "statement_count": 8, "topic_count": 2, "relation_count": 1, "problem_count": 1,

  "documents": [                         // one entry per source document, written once
    { "id": "email-thread-2026-07-05", "type": "email", "date": "2026-07-05",
      "people": ["Marko Virtanen", "Petra Lindqvist"], "summary": "Go-live date moved…" }
  ],

  "topics": [                            // every statement lives in exactly ONE topic
    {
      "topic": "go-live-date",
      "summary": { "text": "Go-live moved from October 1st to November 15th…",
                   "statements": ["email-thread-2026-07-05#1"] },   // what the sentence rests on
      "relations": [                     // stored once, on the topic they belong to
        { "from": "email-thread-2026-07-05#1",         // the newer statement …
          "to":   "status-report-2026-06-30#1",        // … acts on the older one
          "kind": "supersedes" }
      ],
      "statements": [
        { "id": "status-report-2026-06-30#1",          // <document id>#<position in it>
          "claim": "The October 1 go-live date remains on track pending final UAT sign-off.",
          "actor": { "name": "Marko Virtanen", "organization": "Nordica Retail" },
          "speech_act": "report",         // proposal | agreement | decision | report | question | objection
          "statement_date": "2026-06-30T09:00:00",
          "status": "stale" }             // derived from the relations above, never from dates
      ]
    }
  ],

  "problems": [                          // places a reader would go wrong
    { "kind": "reversal", "topic": "go-live-date",
      "statements": ["status-report-2026-06-30#1", "email-thread-2026-07-05#1"],
      "note": "The June report says October 1st is on track, but it was moved afterwards." }
  ]
}
```

Three things worth knowing:

- **Direction of a relation.** Read `from → to` as "`from` acts on `to`". So the *`to`*
  statement is the one that gets the status: `supersedes` makes `to` stale, `corrects` makes
  `to` never-true.
- **`id` is `<document id>#<n>`.** The document id is the path under `input/`, and `n` counts
  from 1 inside that document. The same id is used in `statements.json`. A statement's
  document type and date are not repeated on it; look the document up in `documents`.
- **The prose is the risky part.** `summary.text` and `problems[].note` are model-written.
  Statuses, relations and ids are code-checked; prose can only be checked for real ids, no
  quotation and no invented figure. It is also where a deleted person could survive
  (`KEEP_PROSE` in [output.py](../statement_extraction/src/app/output.py) switches it off).

## What the answering model is shown

The file above is the *stored* form. The backend re-shapes it for the model on every
question ([llm_client.py](../backend/src/app/llm_client.py), decision D45), because
what the model reads is what costs tokens:

```jsonc
{
  "people":  { "p1": ["Marko Virtanen", "Nordica Retail"], "p2": ["Petra Lindqvist", "RELEX"] },
  "columns": ["id", "who", "speech_act", "date", "status", "links", "claim"],
  "topics": [
    { "topic": "go-live-date",
      "statements": [
        ["s1", "p1", "report",   "2026-06-30", "stale",   ["superseded-by:s2"], "The October 1 go-live date remains on track…"],
        ["s2", "p1", "decision", "2026-07-05", "current", [],                   "Marko Virtanen decided to move the go-live date to November 15th…"]
      ] } ]
}
```

- A statement is one **row**; `columns` names the cells once.
- **`people`** is a speaker table keyed by *(name, organisation)*, so the same name at two
  organisations is two entries.
- **`links`** is the relations, read from the side of the statement they land on:
  `superseded-by`, `corrected-by`, `answered-by`, `conflicts-with` (a conflict shows on both).
- **`s1`, `s2`, …** are short aliases for the real ids, made fresh on every call.
- Topic summaries and problem notes are **not** sent: the status and links already say what
  they say.

## How a citation gets back to the screen

The model never writes a citation. It writes `[1]` markers and a list of the aliases it used
(`["s1", "s2"]`). The backend looks each alias up in its own loaded copy of the file, and
anything it did not hand out is dropped. What goes to the frontend is copied from that copy:

```jsonc
{ "marker": 1,
  "statement_id": "status-report-2026-06-30#1",  "document_id": "status-report-2026-06-30",
  "claim": "The October 1 go-live date remains on track…",
  "actor": { "name": "Marko Virtanen", "organization": "Nordica Retail" },
  "speech_act": "report",
  "statement_date": "2026-06-30T09:00:00", "document_date": "2026-06-30",
  "status": "stale",                               // null when answering from statements.json
  "status_receipts": ["email-thread-2026-07-05#1"] } // the statements that justify that status
```

The frontend renders the status pill from `status` and "Because of …" from `status_receipts`.
Nothing about this shape changed with D45; a test
(`test_a_model_reply_becomes_citations_the_frontend_can_render`) pins it.

## Where to look

| | |
|---|---|
| Why the pass exists, what it rejected | D40, D42 in [decisions.md](decisions.md) |
| Why the stored file is shaped this way | D44 |
| Why the model is shown rows, not this JSON | D45 |
| Full plan and failure analysis | [plans/second-pass-reconciliation.md](plans/second-pass-reconciliation.md) |

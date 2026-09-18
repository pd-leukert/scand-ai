# What a statement records

Conceptual only. This is the list of things we decided every statement must carry, and the
reasoning behind each one. It is **not a schema** — field names, types and structure get
fixed once we have seen the real documents, and this page gets updated then.

## The unit

One **statement** is one thing one person asserted, proposed, agreed to, decided or
reported, in one place in one document. Not a paragraph, not a topic, not a decision:
a single speech act located in the record.

Statements are the only thing the answering side ever sees. If it is not a statement, it
does not exist as far as the agent is concerned.

## What each statement carries, and which slice of the rubric it serves

### Where it came from — *provenance, 25%*

- **The document** it came from, by stable identifier.
- **Where in that document**: page and line for PDFs, line range for text files. The
  judges' phrase is "and where in it", so the document alone is not enough.
- **The verbatim span** it was extracted from — the actual words on the page. This is
  what we show the judge when they check a citation, and it is our own check against the
  model paraphrasing something into existence.

### Who said it, and for whom — *attribution, 20%*

- **The actor**: the person the document attributes it to.
- **Their organisation and role as of that document.** Not their current role. People
  changed jobs over the year covered by the corpus, and "did the customer agree" is a
  question about who they were in the room, not who they are now.
- **Who agreed, if anyone.** For statements that record agreement, the parties. The
  answer "nobody ever agreed to this" is a correct and valuable answer, and we can only
  give it if the absence is represented.

### What kind of claim it is — *attribution, 20%*

A **speech-act type**: proposal, agreement, decision, report, question, objection.
This is the distinction the brief calls out by name — a consultant floating an idea is not
the customer agreeing to it — and it is a property of the statement, decided once at
extraction time, not something the answering model should re-litigate per question.

### When — *currency, later*

- **The date of the statement**, and separately the date of the document containing it,
  because a status report written in June can describe a decision made in March.

Dates alone do not solve currency; they are a necessary input to the reconciliation pass
that will. See [roadmap.md](roadmap.md).

## What is deliberately absent from the MVP

- **Status** (current / stale / never-true) and **links between statements**
  (supersedes, contradicts, retracted-by). These are the output of a second pass over the
  aggregated set that we are not building yet. Nothing in the MVP should pretend to know a
  statement's status.
- **People as first-class records.** Actors are described on each statement rather than
  referenced from a registry. This is the main thing that makes deletion a sweep over
  statements rather than a single operation, and it is a known cost of the MVP shape.

## What deletion has to touch

Recorded here because it constrains the model: a deleted person's name can appear in the
actor fields, in the agreed-by parties, *and inside the verbatim span*. The span is the
part people forget. A redaction that leaves the quoted line intact publishes the name in
the citation — the one place we are guaranteed to show the judge.

See [decisions.md](decisions.md) D3 for what we replace names with, and
[roadmap.md](roadmap.md) for the residual risk we are accepting.

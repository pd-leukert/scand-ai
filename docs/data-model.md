# What a statement records

Conceptual only. This is the list of things we decided every statement must carry, and the
reasoning behind each one. It is **not a schema** — field names, types and structure get
fixed in code. What the source documents actually look like, which is what the location
fields have to survive, is in [corpus.md](corpus.md).

## The unit

One **statement** is one thing one person asserted, proposed, agreed to, decided or
reported, in one place in one document. Not a paragraph, not a topic, not a decision:
a single speech act located in the record.

Statements are the only thing the answering side ever sees. If it is not a statement, it
does not exist as far as the agent is concerned.

## What each statement carries, and which slice of the rubric it serves

### Where it came from — *provenance, 25%*

- **The document** it came from, by stable identifier.
- **Where in that document.** The corpus is 45 plain-text files, so the base pointer is a
  line range. On top of that, each genre has a better pointer and we take it:
  - **transcripts** — the utterance offset the Teams export already prints
    (`Marco Rossi 1 minute 4 seconds`). This is literally the "position in the
    conversation" the brief asks for.
  - **email threads and status reports** — *which message in the thread*. A thread is one
    file holding up to eighteen messages from five people across months, so the filename
    alone points at almost nothing.

  The judges' phrase is "and where in it". The document alone is not a receipt.
- **The verbatim span** it was extracted from — the actual words in the file. This is
  what we show the judge when they check a citation, and it is our own check against the
  model paraphrasing something into existence. Two rules that follow from the corpus:
  **quote the garbled transcription as it stands** rather than cleaning it up (the judge
  diffs the span against the file), and **never build a span out of an attachment
  placeholder, a signature block or the synthetic-data banner** — those are holes in the
  record, not claims. There are four placeholder forms, including a bare `Image` and a
  Swedish one, so this is not a single-string match ([corpus.md](corpus.md)).
  The same goes for a figure the speaker never finished: quote the fragment, record that
  the number is incomplete, and do not let the model finish it.

### Who said it, and for whom — *attribution, 20%*

- **The actor**: the person the document attributes it to — as a *person*, not as the
  string that happened to appear. One person in this corpus is spelled two ways
  (`Henrik Sørensen` / `Henrik Sorensen`) and two different people share a first name
  (`Nadia Haddad`, `Nadia Öberg`). Attribution and deletion both break on a model that
  treats the spelling as the identity. See D19.
- **Unknown is a value.** Three internal transcripts are one-to-one recordings whose
  speakers are exported as `Me:` and `Them:`; three more contain `Unknown Speaker`. The
  attendee header names who was in the room, which is not the same as who said the line.
  The actor there is unknown, and it must be *recordable* as unknown — guessing from the
  attendee list is exactly the invented attribution the rubric punishes.
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

### What document it sits in — *provenance and initiative*

The documents carry usable metadata and it is free: transcripts have
`Meeting / Customer / Date / Phase / Attendees`, threads have subject, participants and
message count. Two things worth carrying onto the statement beyond the document id:

- **The document's date**, separately from the statement's (below).
- **Its audience.** Three transcripts are RELEX-internal and one has the partner in the
  room. Nothing else in the corpus is marked. If we build the audience-scoped answering
  feature this is the field it runs on; if we do not, it is still the difference between
  quoting an internal account review to a customer and not. See [roadmap.md](roadmap.md).

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
actor fields, in the agreed-by parties, *and inside the verbatim span* — under **any of
their spellings**, and next to a different person who shares their first name. The span is
the part people forget; the spelling variant is the part that fails
silently. A redaction that leaves the quoted line intact publishes the name in
the citation — the one place we are guaranteed to show the judge.

See [decisions.md](decisions.md) D3 for what we replace names with, and
[roadmap.md](roadmap.md) for the residual risk we are accepting.

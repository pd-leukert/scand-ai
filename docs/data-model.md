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

**As of D37, the persisted statement carries neither a location nor a verbatim span, and
neither a role nor an agreed-by list.** The sections below describe the rubric this corpus
was designed to score and are kept for that reason, but the *provenance* and part of the
*attribution* slice they describe are no longer backed by what the file actually stores —
see D37 for what was cut, at whose direction, and what it costs.

### Where it came from — *provenance, 25%, not currently delivered*

- **The document** it came from, by stable identifier. This part still holds.
- ~~**Where in that document.**~~ Not stored. The corpus is 45 plain-text files, so the
  natural base pointer was a line range, with a genre-specific pointer on top of it (the
  Teams export's utterance offset for transcripts, "message N of M" for threads and
  reports) — this is what the judges' phrase "and where in it" asks for, and it no longer
  exists on a statement.
- ~~**The verbatim span** it was extracted from~~ — Not stored. This was what a judge
  could diff against the source file to check a citation, and extraction's own defence
  against the model paraphrasing something into existence; it still guards extraction
  internally (span-matching still runs, so a hallucinated claim is still dropped before it
  reaches the file — see `statement_extraction/src/app/extraction.py`), but the verified
  span itself is not written out, so nothing downstream can show it.

### Who said it, and for whom — *attribution, 20%, partly delivered*

- **The actor**: the person the document attributes it to — as a *person*, not as the
  string that happened to appear. One person in this corpus is spelled two ways
  (`Henrik Sørensen` / `Henrik Sorensen`) and two different people share a first name
  (`Nadia Haddad`, `Nadia Öberg`). Attribution and deletion both break on a model that
  treats the spelling as the identity. See D19. This part still holds.
- **Unknown is a value.** Three internal transcripts are one-to-one recordings whose
  speakers are exported as `Me:` and `Them:`; three more contain `Unknown Speaker`. The
  attendee header names who was in the room, which is not the same as who said the line.
  The actor there is unknown, and it must be *recordable* as unknown — guessing from the
  attendee list is exactly the invented attribution the rubric punishes. This part still
  holds.
- **Their organisation** as of that document. Still stored. ~~**and role**~~ — not stored
  (D37); extraction still asks the model for it and validates it against the document's
  own words, but `output.py` no longer writes it out.
- ~~**Who agreed, if anyone.**~~ Not stored (D37). "Nobody ever agreed to this" is no
  longer a representable answer distinct from "an agreement statement doesn't mention
  who" — the answering model has only the agreeing party's own statement (if it was itself
  extracted as an `agreement`/`decision`) to go on.

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

The statements file itself carries these once per document, not once per statement — the
document id, type, date, the people involved (its `Attendees:` header, or a thread's actual
senders) and a summary (its `Meeting:` or `Subject:` line). Only what genuinely varies
statement to statement repeats on each one — as of D37, that is just claim, actor, speech
act and statement date. See [decisions.md](decisions.md) D36 and D37.

### When — *currency*

- **The date of the statement**, and separately the date of the document containing it,
  because a status report written in June can describe a decision made in March.

Dates alone do not solve currency. The reconciliation pass (D42, below) reads them for
exactly one thing: ordering statements for the model, and rejecting a `supersedes` link
that runs backwards in time. See [roadmap.md](roadmap.md).

## What the reconciliation pass adds

A second pass over the aggregated statements (D42) writes a second file. It does not change
a statement; it wraps them. A plain-words walkthrough with an annotated example is in
[reconciled-file.md](reconciled-file.md).

- **Topics.** Every statement is in exactly one topic, a short kebab-case subject tag
  (`bakery-workstream-scope`). Statements the pass could not tag sit in one `untagged`
  topic and are never compared with anything.
- **Relations**, stored once on their topic, each naming two statement ids in it:
  `supersedes` (a later statement replaces what an earlier one said), `corrects` (one
  statement says another was wrong when it was recorded), `conflicts-with` (they cannot
  both be true and nothing settles which), `answers` (one settles a proposal or question).
- **A status on each statement**, derived by code from the relations and never from dates:
  `never-true` if something corrects it, else `stale` if something supersedes it, else
  `disputed` if it conflicts with something, else `unresolved` if it is a proposal or
  question nothing answers and nobody accepted, else `current`. `never-true` outranks
  `stale` because reporting a record that was never true as merely old is one of the
  failures the brief names.
- **A one-sentence summary per topic** and **a list of problems** (reversal, never-true,
  conflict, unanswered), each naming statement ids. These are the only model-written prose
  in the file, and each has to name real statements or is dropped.

**The file is reduced the way the statements file is (D36, D37, D46).** What is true of a
whole document — its id, type, date, people and summary — is written once, in a `documents`
table. A statement carries only `id`, `claim`, `actor` (name, organization), `speech_act`,
`statement_date` and its `status`: no `document_id`, `document_date`, location, verbatim span,
`agreed_by`, `handling`, or actor label and role. The id stays, unlike in the statements file,
because relations, problems and summaries point at it and the statements here are laid out by
topic, so position cannot give it back. The backend restores `document_id` (the id up to its
`#`) and `document_date` (from the table) on load. What the answering model is shown is
smaller again: each statement under a short alias (`s1`, `s2`, …) mapped back to its real id on
our side, so a long id is not repeated in every relation, problem and receipt that names it.

Nothing here is a new quote: a relation, receipt or problem that does not name a statement
the first pass produced is thrown away, and a status no surviving relation justifies is
overruled. `current` is what an unlabelled statement is, and it means only that nothing we
grouped with it contradicts it.

## What is still deliberately absent

- **People as first-class records.** Actors are described on each statement rather than
  referenced from a registry. This is the main thing that makes deletion a sweep over
  statements rather than a single operation, and it is a known cost of the MVP shape.

## What deletion has to touch

Recorded here because it constrains the model: a deleted person's name can appear in the
actor fields *and inside the claim* — under **any of their spellings**, and next to a
different person who shares their first name. The claim is the part people forget; the
spelling variant is the part that fails silently. A redaction that leaves the claim's text
intact publishes the name in the citation — the one place we are guaranteed to show the
judge. (Before D37 this warning was about the verbatim span; there is no verbatim span any
more, but the claim is exactly as capable of quoting a name back at a judge, so the same
rule applies to it.)

Since D42 there are **two** derived files, and both have to be redacted. The reconciled
file nests every statement, so it repeats every span and actor field the statements file
has. It also holds model-written prose — the topic summaries and problem notes — where a
name can sit in a sentence rather than in a span, and where matching the span will not find
it. The backend also caches what it loads, so deletion has to clear that cache or a warm
process keeps answering with the name.

See [decisions.md](decisions.md) D3 for what we replace names with, and
[roadmap.md](roadmap.md) for the residual risk we are accepting.

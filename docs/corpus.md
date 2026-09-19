# The corpus — what is actually in the archive

The archive arrived with the Friday handout and sits in [`input/`](../input/). Everything
on this page was checked against the files, not taken from the brief or the handout.
Numbers were current on 2026-09-19; re-check them if `input/` changes.

The handout's own manifest — file list, message counts, the cast — is copied verbatim at
[archive-readme.md](archive-readme.md), and the nine practice questions at
[practice-questions.md](practice-questions.md). **Where the manifest and the files
disagree, the files win**; the differences are noted below.

Read this before writing extraction code. Half the planted difficulty in this challenge is
in the file formats, and it is cheaper to read about it than to discover it at 2am.

## Shape and size

| | |
|---|---|
| Files | **45**, all `.txt`, UTF-8 |
| `input/transcripts/` | 23 Teams meeting exports |
| `input/emails/` | 20 email threads |
| `input/reports/` | 2 status-report threads (weekly and monthly), email-shaped |
| Total | ~59,000 words, ~363,000 characters (the handout says ~57,000 words; the difference is banners and signature blocks) |
| Span | 2024-03-20 (first sales demo) → 2026-07-02 (internal renewal planning) |

~363k characters is roughly 90k tokens by the usual rule of thumb — **unmeasured, and the
number that matters is the size of the derived file that goes into the model's context, not the corpus.** But it is the
reason the brief says the archive fits in a long context window, and it is the evidence
behind D2 (no retrieval).

There are no PDFs. There are no attachments — and the handout warns explicitly: **do not
match on one string.** Images and diagrams appear in the emails and reports as four
different placeholders:

| Form | Count |
|---|---|
| `[Image removed by sender]` | 158 |
| a bare `Image` on its own line | 118 |
| `[cid:image001.png]` | 15 |
| `Bild borttagen av avsändaren` (Swedish) | 10, across three threads |

**Never emit a statement whose span is an attachment placeholder** — it is a hole in the
record, not a claim, and citing one is citing nothing. The transcripts contain no
placeholders at all; this is an email-and-reports problem only.

Every file opens with a `*** SYNTHETIC DATA` banner. It is not content; extraction should
skip it.

## The cast

Invented people, invented company. Acme Org is an EMEA grocery retailer; Meridian
Consulting is the partner; RELEX is the vendor and is named throughout.

Roles below are the handout's, and they are the roles *as introduced* — see the warning
under the table.

| Organisation | Who |
|---|---|
| **Acme Org** (customer) | Lena Fischer (Head of Supply Chain), Robert Kahn (CFO), Sofia Almeida (Category Manager, Fresh), Priya Nair (IT Integration Lead), Jonas Weiss (Category Manager, Ambient), Katarina Voss (Data Protection Officer) |
| **RELEX** (vendor — us, and the judges) | Marco Rossi (Account Executive), Ana Duarte (Project Manager), Nadia Haddad (Solution Consultant), Tomas Lindholm (Solution Architect), Kwame Boateng (Technical Consultant), Charlotte Meyer (Service Delivery), Henrik Sørensen (Account Director) |
| **Meridian Consulting** (partner, bakery workstream) | Ivan Petrov, Ruth Oyelaran |

Two people appear in the files but not in the handout's cast list: **Priyanka Rao** (RELEX
People Partner, transcript 23) and **Nadia Öberg** (mentioned once — see trap 3). Do not
treat the manifest as a closed set of people.

Roles move over two years. Attribution has to use the role as of the document, never a
person's latest role.

## File formats

### Transcripts — `input/transcripts/NN_YYYY-MM-DD_slug.txt`

A header block, then the conversation:

```
Meeting: Solution demo & value workshop
Customer: Acme Org (Grocery Retail, EMEA)
Date: 2024-03-20
Phase: Pre-Sales
Attendees: Lena Fischer (Acme), Sofia Almeida (Acme), Marco Rossi (RELEX), Robert Kahn (Acme CFO, joins late)

Marco Rossi
1:041:04
MR
Marco Rossi 1 minute 4 seconds
Thanks for the time today. Can everyone hear me?
```

All 23 have `Attendees:`. `Phase:` is one of `Pre-Sales` (3), `Implementation` (10),
`Live-Services` (8), `Internal (RELEX only)` (2).

The repeated speaker name, the doubled timestamp (`1:041:04`), the initials and the
spelled-out offset (`1 minute 4 seconds`) are all artefacts of the Teams export. The
spelled-out offset is the **position in the conversation** the brief asks us to cite, and
it is per utterance — the best location pointer in the corpus.

### Emails and reports — `input/emails/`, `input/reports/`

Outlook exports. One thread per file, **reverse chronological, with every earlier message
quoted beneath** — each message carries `From: / Sent: / To: / Cc: / Subject:` headers,
and the top one additionally `Date:` and `Messages in thread: N`. Threads run from 3 to 12
messages; per-file counts are in [archive-readme.md](archive-readme.md).

The two report files are the same format: `01_weekly-status-thread` holds 18 weekly
updates (Jun 2025 – Apr 2026) with `🟢 On Track` / `Slight Delay` markers and week
numbers; `02_monthly-steering-reports` holds 7 monthly reports to the CFO
(Jul 2025 – Apr 2026).

So a thread has **no single date and no single author**. A citation that names the file and
nothing else points at up to eighteen messages by five people across months. The location
has to resolve to one message.

Signature blocks, the `This email originated from outside of RELEX` banner, and the
marketing footer repeat on nearly every message. They are noise, and they are also a
tempting thing for an extractor to turn into statements.

## The planted messiness

The brief names five traps. All five are in the files, and they are specific:

1. **Speech-to-text errors.** Restarts, filler, and repeated half-sentences
   (`Go-live is in. DC-1, the pilot group.`), and garbled numbers — one contract value is
   transcribed as `nine hundred and eighty eighty thousand annual`. A verbatim span will
   sometimes be verbatim nonsense. Quote it anyway; do not clean it up in the span, because
   the span is what the judge checks against the file.
2. **One person, two spellings.** `Henrik Sørensen` (49) and `Henrik Sorensen` (4). One
   RELEX Account Director.
3. **Two people, one first name.** `Nadia Haddad` (RELEX, throughout) and `Nadia Öberg`
   (mentioned once). The archive disambiguates them in exactly one line, in an internal
   transcript: *"like Nadia Haddad, employee four. Not Nadia Öberg."* If a judge asks us to
   delete "Nadia", that line is the whole ballgame — see D19.
4. **Decisions changed without anyone flagging it.** The stale half of the currency slice.
5. **Records that were wrong when written.** The never-true half. Date order cannot
   separate 4 from 5.

And two more that the brief does not name but the files contain:

6. **Three transcripts have no speaker names at all.** The internal ones —
   `04_…INTERNAL-handover`, `09_…INTERNAL-account-review`, `23_…INTERNAL-renewal-resourcing` —
   are one-to-one recordings exported with `Me:` and `Them:` as speakers. The attendee
   header names two or three people; the body attributes nothing. Attribution for those
   utterances is genuinely unknown and must be reported as unknown, not guessed from the
   header.
7. **`Unknown Speaker`** appears in three further transcripts (03, 17, 18). Same rule.

8. **Numbers that get cut off mid-sentence.** The practice questions warn about this
   directly: *"an agent that completes the sentence for them has invented a source."* The
   clearest case is in `07_2024-11-12_ordering-logic-design`, at 8 minutes 15 seconds:

   > Kwame Boateng: *"Where we have it. Remediation is at about sixty"*

   Sixty what, of what, is not in the record — the next speaker says "Yeah." A master-data
   remediation percentage is exactly what P1 and P5 ask for, so this is bait. The correct
   behaviour is to quote the fragment and say the figure is incomplete.

## Access markers — free metadata

Three transcripts are marked `INTERNAL` in the filename (and two of those also in
`Phase:`); one is marked `PARTNER` and has Meridian Consulting in the room. Nothing else
in the corpus carries a visibility marker, so this is a small but real signal: the same
question has different correct answers for an account manager, an implementation
consultant and someone from the partner firm. It is the cheapest support in the archive
for one of the brief's suggested initiative features — see [roadmap.md](roadmap.md).

## One thread worth knowing before the demo

`input/emails/04_march-2024-notes-correction.txt` is a four-message thread in which Sofia
Almeida asks RELEX to remove one sentence about her health from a derived document
(`Acme-fresh-handover-v3`, page 4), explicitly asks that a *different* fact about her be
kept, and is told the old version survives in the project site's document history where
the sender cannot delete it.

It is the challenge's own premise, planted inside the archive: a derived artifact that
outlived the record it came from, and a deletion that is about one fact rather than one
person. Useful in the demo, and a reminder that the corpus is about people, not rows.

## What the practice questions tell us about the archive

The nine questions ([practice-questions.md](practice-questions.md)) are not the graded set,
but they are written by the people who planted the traps, so they double as a map:

- **P1, P5** — master-data completeness and shelf-life coverage have *several* figures
  across several documents. Expect to have to list all of them with dates, not pick one.
- **P3** — the operator-ID field removal (`emails/07_op-id-field-exclusion`) is the
  attribution set piece: who proposed, who agreed, and whether the data had already gone
  out before anyone agreed.
- **P4** — UAT sign-off (`emails/15_uat-signoff`) is a scope trap: something was signed,
  but not the thing the question sounds like it is asking about.
- **P6** — bakery in or out of the fresh workstream is the stale-decision set piece; it
  changes across transcripts 17, 19 and 20.
- **P7** — the deletion target they chose for practice is **Kwame Boateng**, a RELEX
  Technical Consultant who is also the speaker in trap 8 above and a source for P1. They
  picked someone whose removal breaks a provenance answer. Rehearse this one.
- **P9** — three weekly updates state *"Nightly article extract completed, no errors"*.
  The reports are evidence that the extract **reported** success, not that the data was
  right. This is the never-true case, and it is the one question where a correct citation
  and a wrong conclusion score nothing.
- **Two of the nine have no clean answer.** They are not saying which.

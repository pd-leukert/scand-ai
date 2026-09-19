# Deletion — what the `shah/deletion` branch does, and where it stands

Update this page in place as the branch moves. It is a status page, unlike
[decisions.md](decisions.md), which is append-only. The design is in [D3](decisions.md),
[D19](decisions.md), [D37](decisions.md), [D38](decisions.md) and [D39](decisions.md); this page says what is built and what is left.

## In one paragraph

Deletion changes the derived file, `statements.json`, so a deleted person is gone from the data
the answering path reads (working agreement, rule 3). A request such as "Kwame Boateng" is first
resolved to one person. Every spelling of that person is then replaced by a role-class
placeholder, such as `[former RELEX employee]`, in the speaker fields, the agreed-by names, the
quoted words and the claim. The neighbouring statements survive, so the decisions around the
person keep answering. A receipt says who was removed and who was left. It is pseudonymisation,
not erasure, and the demo says so out loud.

## Where it stands

| Step | State |
|---|---|
| 1. The redaction function and its tests | Done. Committed on this branch. |
| 2. A command that rewrites `statements.json` in place and prints the receipt | Done. `python -m src.app.delete`, see "Try it". |
| 3. How the demo triggers a deletion | Needs a team decision, see below. |
| 3b. The backend answers from the rewritten file without a restart | Done. It reads the file on every request (D39). |
| 4. Try it on the real `statements.json` from the full extraction run | Half done. Run on a file of the real shape, see "Checked against the real shape". The real model's run is still to come. |
| 5. Show the receipt in the frontend, then keep answering | Not started. Frontend work. |
| 6. Rehearse on Kwame Boateng (practice question P7), Nadia and Henrik | Not started. |

## What is in the branch

| Path | What it is |
|---|---|
| `statement_extraction/src/app/deletion.py` | `delete_person(statements, request)` returns the redacted statements and a receipt. It reads nothing else and keeps nothing. |
| `statement_extraction/tests/test_deletion.py` | 15 tests: the three name traps, emails, quotes, placeholders, an unknown name, a second deletion. |
| `statement_extraction/src/app/delete.py` | The command: reads and writes `STATEMENTS_FILE_PATH`, prints the receipt, `--dry-run` changes nothing. |
| `backend/src/app/statements.py`, `backend/tests/test_statements.py` | The backend reads the file on every request and reads it as UTF-8 (D39). 2 tests. |
| `statement_extraction/tests/test_delete_command.py` | 7 tests: the rewrite, non-ASCII names surviving, dry run, an unknown name, a repeat, a missing file, a leftover `documents/` folder. |
| `docs/decisions.md` | D37: the design. D38: the command. What was rejected, what it costs. |

## How it works

1. **Resolve the person from the statements.** The names come from the speaker and agreed-by
   fields, plus "First Last" pairs in the text whose first name belongs to a known speaker. That
   is how Nadia Öberg, who is only mentioned once, is found. Spellings that differ only by
   accents are one person. An exact full name wins. A bare first name picks the person with the
   most statements. A speaker the file only labels, such as `Guest 1`, is never a person.
2. **Replace, most specific first.** The full name in either order, then an email
   (`first.last@`, `f.last@`, `last.first@`), then the last name and first name on their own.
   A bare name is replaced only if nobody else in the file shares it. Otherwise it is left, and
   the receipt says who shares it.
3. **Sweep every string field** except ids, dates, `position`, `speech_act`, `handling` and
   `doc_type`. A field added later is covered by default.
4. **Return a receipt.** It is for showing, and is not stored.

The receipt for "Nadia" on the real archive text:

```
deleted:        Nadia Haddad, replaced with [former RELEX employee]
considered:     Nadia Haddad (350 statements) removed, Nadia Öberg (1 statement) left
left in place:  "Nadia" on its own: also the name of Nadia Öberg
```

## Try it

Run the tests:

```
cd statement_extraction
uv run pytest
```

Delete a person from the statements file (`STATEMENTS_FILE_PATH`, default `statements.json`). Add
`--dry-run` to see the receipt and change nothing:

```
uv run python -m src.app.delete "Kwame Boateng" --dry-run
uv run python -m src.app.delete "Kwame Boateng"
```

In compose, where the extraction container is the only one that can write the file:

```
docker compose run --rm --no-deps statement-extraction uv run --frozen python -m src.app.delete "Kwame Boateng"
```

The receipt goes to the terminal and is stored nowhere. There is no backup, so the rewrite cannot
be undone. Exit code 0 is done, 1 is nobody by that name (the file is untouched), 2 is no file.
The backend reads the file on every request, so the next answer already uses the rewrite.

## Checked against the real shape

`main`'s extraction takes a model callable, so the real code can run with a scripted model. That
gave a file of 1,116 statements from all 45 documents, made by the real parser, span matching,
`agreed_by` linking and `to_statement()`, with one scripted statement per speaker turn. Deleting
Kwame Boateng, Nadia and Henrik Sorensen from it:

- Kwame Boateng: 55 statements as speaker, 63 changed in all, no part of the name left anywhere.
- Nadia: resolves to Nadia Haddad, leaves Nadia Öberg, and the 23 bare "Nadia" strings that
  survive are the ones the receipt reports.
- Henrik Sorensen: resolves to Henrik Sørensen and replaces both spellings.
- Same ids and field shapes out as in, every `agreed_by.statement` still points at a real
  statement, and the input list is not modified.
- The redacted file loads in the backend's own `StatementsFile` model.

## Known limits

- **Pseudonymisation.** If only one RELEX consultant is in a meeting, `[former RELEX employee]`
  identifies them by elimination, and role and organisation stay (D3).
- **A shared first name stays.** Deleting Nadia Haddad leaves "Nadia" on its own in about 23
  places, because it could mean Nadia Öberg. The receipt says so.
- **Phone numbers are not covered.** Nothing in a statement ties a number to a person. The
  receipt says how many statements contain one.
- **Email forms are patterns.** An unusual address form survives.
- **A false person is possible.** A capitalised pair that starts with a known first name is taken
  for a person. On this archive the only extra one it finds is Nadia Öberg.
- **Not yet run on the real model's output.** The checks above use the real record shape, but the
  spans and claims were scripted, so how the model words a claim about a person has not been seen.
- **An interrupted extraction run leaves an unredacted copy.** Extraction writes one file per
  document into a `documents/` folder next to `statements.json` and removes it only after a clean
  run. If a run stops partway, those files hold every name and deletion does not reach them. This
  is the second-artifact problem of working agreement rule 4, on a path we do not own. Nobody has
  decided who fixes it.

## Decisions the team has to make

Both are written up with the options in [open-questions.md](open-questions.md).

1. **How a judge triggers a deletion on the deployed app (Q4).** The command works, but judges use
   the app themselves, and the page cannot call a command. It needs something the frontend can
   reach, without giving the backend a write path.
2. **What stops our own tooling from undoing a deletion (Q5).** `docker compose up` re-runs
   extraction, which would bring a deleted person back, and an interrupted run leaves a
   `documents/` folder holding every name.

## Not planned

Purging the source documents, dropping every statement that mentions the person, and a query-time
filter are all rejected in [D3](decisions.md). A separate people registry is a second derived
artifact, which deletion would have to cascade into, so it is out for now ([D19](decisions.md)).

# What's left

A snapshot from Saturday 19 September 2026. Submissions close **Sunday 12:00**
([demo.md](demo.md)). Update this page in place as things change — unlike
[decisions.md](decisions.md), it is not append-only. Owners below come from the whiteboard and
the git history; confirm them.

## The chain that has to work

```
full extraction run ──► statements file ──► answering backend ──► frontend with receipts ──► public URL
   (needs a GPU)                                                                            on Verda
```

If any link is missing, the judges see nothing. Deletion sits on top of the chain, and the
practice answers are produced from it.

## State of each part

| Part | State | Who |
|---|---|---|
| Extraction (C1) | Built and tested. Verified in Docker on one transcript. The full corpus has not been run. Branch `shah/extraction-pipeline`. See [extraction.md](extraction.md). | Shah |
| Answering backend | A real `POST /query` exists on branch `niek/backend`, not merged: it builds the prompt from the statements file and resolves citations in code from statement ids. Tried only against mock data. On `main` it is still a stub. | Niek |
| Frontend | A placeholder page on `main`. No work is visible in the repo. | Andrea |
| Docker, CI/CD, cloud | Compose is merged (PR #5). Nothing is visibly deployed and no Verda instance is known. | David |
| Deletion | Not built. Nobody is named. | ? |
| Practice answers and demo | Not started. | ? |

## Blockers, in order

### 1. No GPU, so no full extraction run

Nothing downstream has real data until the 45 documents are extracted. On a laptop it is over
ten hours; on a GPU it should be minutes to an hour. Check **Compute → Instances** in the Verda
console, and ask the project owner before creating one: instances draw on a shared balance.

### 2. Extraction and the backend format: matched on our side, two small things left

The two were written separately, and the backend's own doc calls its shape interim
([D10 on `niek/backend`](decisions.md)). Extraction now writes the backend's field names and file
shape ([D21](decisions.md), [D22](decisions.md)). The backend's own loader reads real job output
as it is, with no change on Niek's side. That was checked on a transcript with unnamed speakers, an
email, a report, and an email with linked agreements.

Two things are still open, and neither blocks anything:

- **The path setting** is `STATEMENTS_PATH` in extraction and `STATEMENTS_FILE_PATH` in the
  backend. Compose has to set both to the same file.
- **Unknown values are text, not null.** The backend requires a name, organisation and role for
  every speaker. A speaker the archive does not name is shown by the label the file uses ("Them",
  "Guest 1"), with `label` set to tell it from a real name, and an organisation or role that no
  document states reads `Not stated`. If Niek allows null, the conversion goes back to null in one
  place, and the answering prompt should meanwhile read `Not stated` as no information.

The backend ignores the extra fields (`position`, `claim`, `handling`, `doc_type`, `label`). The
frontend can show `position`, for example "12 minutes 53 seconds", only if the backend passes it
through in citations. That's a small change on his side.

### 3. The whole statements file probably does not fit in context

[D2](decisions.md) puts the whole file in the answering model's context. A rough estimate from
one document: a 789-word transcript produced 38 to 48 statements, and the corpus is about 58,600
words, so somewhere around 2,000 to 3,600 statements. At 350 to 525 bytes a record that is
roughly 1 to 2 MB, hundreds of thousands of tokens, and more if the backend base64-encodes it as it
does now. This is a rough figure from one unusually dense document, so it needs measuring on the
real run. If it holds, D2 does not survive, and the two-stage answer in [roadmap.md](roadmap.md)
or the whiteboard's RAG store is needed. Either way it needs a superseding decision, and any new
store needs a deletion cascade (working agreement, rule 4).

### 4. Decision numbers collide

`niek/backend` has its own D10 and D11, and `main` already has a different D10 (Python 3.12) and
D11 (one Dockerfile per service). This branch adds D14 to D19. Whoever merges second renumbers.

### 5. How the corpus reaches Verda is undefined

[D13](decisions.md) says "external shared storage", but no such storage is visible in the
console. The working plan is a plain copy to the VM ([extraction.md](extraction.md)).

## Checklist

### Extraction (C1)

- [x] Parsers, quote matcher, extraction step, job, compose layers, tests (49), docs
- [x] Container verified in Docker on one transcript; every citation checked against the source
- [ ] Commit and push the latest changes
- [x] Run one email and one report through the job (67 statements, every citation checks out)
- [x] Fill in who agreed with a second pass, with a receipt for each agreement ([D20](decisions.md))
- [ ] Fill in role and organisation from signatures: the model got only 9 of 21 in the email
- [ ] Check the linking pass on transcripts, where replies are less clear than in an email
- [ ] Full run on a GPU with the real model
- [ ] Measure the statements file in tokens (blocker 3)
- [x] Write the backend's field names and file shape; its loader reads real output ([D21, D22](decisions.md))
- [ ] Fold the compose layers into `compose.yaml` and replace the placeholder command
- [ ] A check of each claim against its quote (claims can be wrong even when the quote is right)
- [ ] The private-material flag ([D19](decisions.md), proposed) needs a bigger model to judge

### Answering backend

- [ ] Rebase `niek/backend` onto current `main`; renumber its decisions
- [ ] Read `position` and `label` through into citations, so the frontend can show them (blocker 2)
- [ ] Optional: allow a null speaker name, organisation and role, then ask extraction to switch back
- [ ] Fit the statements in context, or retrieve them (blocker 3)
- [ ] Point `LLM_BASE_URL` at Ollama on Verda and set `LLM_MODEL`
- [ ] Try the practice questions P1 to P9 against real data

### Frontend

- [ ] A question box that calls `POST /query` and shows the answer with numbered citations
- [ ] Every citation expands, in one click, to the document, position, quote, speaker and who agreed
- [ ] "The record does not say" and "the record conflicts" are shown as answers, not errors
- [ ] No logic in the frontend (working agreement)

### Deletion (20% of the score)

- [ ] Decide who builds it
- [ ] Redact the statements file, not filter at query time ([D3](decisions.md)): the speaker, the
      agreed-by names, the quote and the claim
- [ ] Cover what the archive actually contains: the spelling `Henrik Sorensen`, first names,
      email addresses and phone numbers
- [ ] A placeholder for people from the partner, Meridian Consulting, as well as RELEX and the customer
- [ ] Show a receipt, then keep answering about the person and the neighbouring decisions
- [ ] No second store that still holds the name

### Deployment

- [ ] A GPU instance with Docker and the NVIDIA container toolkit
- [ ] Copy the corpus, run extraction, start the stack
- [ ] A public HTTPS URL for the frontend only; the backend and Ollama stay inside the compose network
- [ ] Reachable from a device that is not ours

### Submission and demo

- [ ] Answers to the nine practice questions, with citations (two have no clean answer)
- [ ] Someone who did not build it asks it three questions
- [ ] The honest-limits list from [roadmap.md](roadmap.md), rehearsed
- [ ] The thing it does unasked: D19 is proposed, the team has not agreed

## Decisions the team has to make

1. **Whether the backend allows null** for a speaker's name, organisation and role (blocker 2). Optional.
2. **D2:** whole file in context, or retrieval or an index. The whiteboard shows RAG, which
   contradicts D2 as written.
3. **D19:** whether flagging private statements is the unasked feature.
4. **Who builds deletion**, and where it runs.
5. **How the corpus reaches Verda** (D13).
6. **Decision numbering** when the branches merge.

## Not planned

Currency, meaning stale versus never-true, is out of scope for the MVP ([D4](decisions.md)).
Three of the nine practice questions (P5, P6, P9) lean on it. The honest answer there is to show
the conflicting statements with their dates and say the record does not settle which is current.

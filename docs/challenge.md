# The challenge, as we read it

Source: RELEX Solutions challenge track, "Memory With a Receipt", AaltoAI Hackathon 2026.
This page is our reading of the brief. Where we interpreted something, it says so.

## Who is asking, and why they care

RELEX Solutions builds the planning software that decides what a supermarket orders, how
much, and when. Their 2030 strategy makes AI agents first-class users across the
business. The challenge is hosted by ATLAS, their central technical-solutions and agentic
operations team, and it is not a toy: provenance, staleness and deletion are the same
problems they have to solve inside Cortex, their own agentic platform, for their own
customer conversations.

Practical consequence for us: the judges have built this before. Hand-waving on the hard
parts will be recognised as hand-waving. An honest "we did not do this, and here is why"
scores better than a confident claim that falls over on the second question.

## The setup

- **45 documents**: transcripts, email threads, status reports, spanning March 2024 to
  July 2026 — from the first sales demo to the second year of live service.
- **People have changed jobs.** Roles are not stable across the corpus. Someone who was a
  consultant in March may be a customer employee in October, or gone entirely.
- **The failure mode to avoid**: a clean summary that is wrong. Three named symptoms —
  reporting a reversed decision as current, calling a suggestion an agreement, and
  repeating a record that was never true.

## The five requirements

1. **Cite everything.** Every claim points at a document, *and where in it*. No citation
   and they treat the claim as a guess.
2. **Suggestion ≠ commitment.** A consultant floating an idea is not the customer agreeing
   to it.
3. **Know stale from wrong.** Some decisions were changed later — those are stale. Some
   records were never true — those are wrong. Sorting by date catches only the first kind.
4. **Delete a person.** Out of the index, the embeddings, and the cached summaries. Then
   keep answering.
5. **Do one thing unasked.** The first four are the floor. Show something the agent does
   on its own initiative.

## How it is scored

| Weight | Slice | What earns it |
|--:|---|---|
| 25% | **Provenance** | Right answer, and you can show which document and where in it |
| 20% | **Attribution** | Who proposed it, who agreed, whether anyone did |
| 20% | **Currency** | Stale decisions flagged; records that were never true not repeated |
| 20% | **Deletion** | Gone from everything you derived, *not filtered at query time* |
| 15% | **Initiative** | The thing it does unasked, plus an honest account of what it cannot do |

## How it is tested

- **We submit a URL.** They open it and use it themselves. This is not a slide review —
  the running thing is the deliverable, so it has to be reachable and it has to work in
  someone else's hands.
- **Live questions on Sunday**, a different set from any practice questions, and **they
  check the citations**. A citation that does not resolve to real text in a real document
  is worse than no citation.
- **Deletion is tested adversarially.** They pick the person. Then they ask about that
  person *and about nearby answers* — meaning the neighbouring decisions, the same
  meetings, the same threads. Two ways to fail: the deleted person is still reachable, or
  everything around them broke.

Submissions close **Sunday 12:00**.

## What this means for our build — the non-obvious bits

**"Where in it" is a pointer, not a document name.** Half the provenance slice is
locating the claim inside the document. Citing `workshop-notes-march.pdf` for a 30-page
transcript is not a receipt.

**"Not filtered at query time" is the whole deletion test.** Any design where the person's
data is still present and a filter hides it will be found, because the judges ask around
the edges. Whatever we do must change the thing we derived.

**"Keep answering" is half of the deletion score.** A system that deletes a person by
dropping every document they appear in will pass the first question and fail the next
three. The neighbouring decisions must survive.

**Currency has two failure modes, not one.** Stale (true then, reversed later) and
never-true (wrong when recorded). A date sort cannot tell them apart, and the deck says so
explicitly — which is a strong hint that the test set contains at least one of each.

**Attribution needs role-at-the-time.** Because people changed jobs, "who agreed" cannot
be answered from a person's current role. It has to be their role in the document where
they spoke.

**The 15% is partly free.** Half of that slice is "an honest account of what it cannot
do". We know our limits already; writing them down well is cheap points and it is the
right thing to do regardless.

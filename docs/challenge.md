# The challenge, as we read it

Sources: the RELEX Solutions challenge track brief *"Memory With a Receipt"* (v3) and the
Friday presentation, AaltoAI Hackathon 2026, Design Factory, Otaniemi. Prize: €2,000 to
the winning team. This page is our reading of both. Where we interpreted something, it
says so. What is actually in the archive is a separate page: [corpus.md](corpus.md).

## Who is asking, and why they care

RELEX Solutions builds the planning software that decides what a supermarket orders, how
much, and when. Their 2030 strategy makes AI agents first-class users across the
business. The challenge is hosted by ATLAS, their central technical-solutions and agentic
operations team, and it is not a toy: provenance, staleness and deletion are the same
problems they have to solve inside Cortex, their own agentic platform, for their own
customer conversations. *(This paragraph is from the Friday presentation, not the written
brief.)*

Practical consequence for us: the judges have built this before. Hand-waving on the hard
parts will be recognised as hand-waving. An honest "we did not do this, and here is why"
scores better than a confident claim that falls over on the second question. The brief
says so outright — *"If part of it doesn't work, show us."*

## The setup

- **45 documents, two years of a rollout**, from the first sales demo to the second year
  of live service: 23 Teams meeting transcripts, 20 email threads, 2 status-report
  threads. Everything is plain text. Details: [corpus.md](corpus.md).
- **Acme Org is invented** — a fictional EMEA grocery retailer. No RELEX customer data is
  involved. RELEX is named throughout and the archive is *not flattering* about how the
  vendor handled things. That is deliberate, and it means we must not soften what the
  record says about RELEX.
- **It is small on purpose.** The brief says the whole archive fits in a long context
  window and that we may skip retrieval plumbing — the weekend is meant to go on the
  scored parts, not on a vector store.
- **People have changed jobs.** Roles are not stable across the corpus. Someone who was a
  consultant in March may be a customer employee in October, or gone entirely.
- **It is messy on purpose**, in ways that are planted and named: speech-to-text errors,
  one person whose name comes out two different ways, two people who share a first name,
  decisions changed later without anyone flagging the change, records that were wrong when
  they were written, and attachments that exist only as placeholders.
- **The failure mode to avoid**: a clean summary that is wrong. Three named symptoms —
  reporting a reversed decision as current, calling a suggestion an agreement, and
  repeating a record that was never true.

## The five requirements

1. **Cite everything.** Every factual claim points at a document, *and for transcripts a
   position in the conversation*. No citation and they treat the claim as a guess.
2. **Suggestion ≠ commitment.** A consultant floating an idea is not the customer agreeing
   to it. The agent should be able to say who said something and whether anybody agreed.
   The brief calls this "the error that does real damage".
3. **Know stale from wrong.** Some decisions were changed later — those are stale. Some
   records were never true — those are wrong. Sorting by date catches only the first kind.
4. **Delete a person.** Out of the index, the embeddings, and any cached summaries. Then
   keep answering everything else. **Everyone else stays named** — this is deletion of one
   person, not anonymisation of the archive.
5. **Do one thing unasked.** The first four are the floor; *"a system that only answers
   questions is a search engine with footnotes."* The brief's own suggestions, which it
   says the archive supports, are in [roadmap.md](roadmap.md) alongside our shortlist.

And a fifth-and-a-half, scored separately from the five: **residency**. The archive stays
in the EU, and we have to say where inference runs and how the documents get there. Local
models, EU-hosted endpoints and EU-region APIs are all acceptable. Send the archive
outside the EU and the sovereignty marks are gone regardless of answer quality. Our
position: [architecture.md](architecture.md#residency).

> **"Get three or four of the five requirements working properly and that's a real entry.
> We'd rather see that than five half-built ones."** This sentence was the licence for D4
> (since superseded by D40) — shipping without a currency signal is an explicitly acceptable
> entry; faking one is not. We now ship one, and it is derived from links, not dates.

## How it is scored

| Weight | Slice | What earns it |
|--:|---|---|
| 25% | **Provenance** | Right answer, and you can show which document and where in it |
| 20% | **Attribution** | Who proposed it, who agreed, whether anyone did |
| 20% | **Currency** | Stale decisions flagged; records that were never true not repeated |
| 20% | **Deletion** | Gone from everything you derived, *not filtered at query time* |
| 15% | **Initiative** | The thing it does unasked, plus an honest account of what it cannot do |

## How it is tested

- **We submit a URL, not a repo.** They open it and use it themselves during grading on
  Sunday morning. This is not a slide review — the running thing is the deliverable, so it
  has to be reachable and it has to work in someone else's hands. If we cannot host it, a
  container they can run is acceptable **but we have to tell them on Saturday**.
- **Deploy in the EU.** Part of the residency requirement, stated under testing.
- **Live questions on Sunday**, a different set from the practice questions, and **they
  check the citations**. A citation that does not resolve to real text in a real document
  is worse than no citation.
- **Deletion is tested adversarially.** They pick the person. Then they ask about that
  person *and about things nearby the deletion might have broken* — the neighbouring
  decisions, the same meetings, the same threads. The brief grades it in three bands:

  | What they find | Marks |
  |---|---|
  | Gone from the index, the embeddings and any cached summaries | Full |
  | Filtered at query time **and declared as a filter** | Partial |
  | Filtered at query time and **called deletion** | None |

  Two ways to fail the first band: the deleted person is still reachable, or everything
  around them broke. Note the third row — overclaiming is worth *less than nothing*, which
  is why D3's honest-limits paragraph is not optional politeness.

## What to submit by Sunday 12:00

1. A deployed agent, with a URL.
2. One thing the agent does unprompted, **working in the deployed version** — not on a
   slide, not on someone's laptop.
3. Our answers to the practice questions, with citations.
4. **One page on the design**: how provenance is stored, how we catch stale facts, how
   deletion propagates, where inference runs. Those four questions, in that order.
5. A five-minute demo and five minutes of questions.

Preparation for all five lives in [demo.md](demo.md).

## Schedule

| When | What |
|---|---|
| Fri 18 Sep | Challenge presentation, archive handout, practice questions released |
| Sat 19 Sep | Mentoring slots morning and late afternoon — **bring the provenance design to the morning one**. Also the day to tell them if we cannot host. |
| Sun 20 Sep | Submissions close **12:00**. Grading until 13:00, pitches after. |

## What this means for our build — the non-obvious bits

**"Where in it" is a pointer, not a document name.** Half the provenance slice is
locating the claim inside the document. Citing `01_2024-03-20_solution-demo-value-workshop.txt`
for an hour of transcript is not a receipt. For transcripts the brief asks specifically for
"a position in the conversation", and the Teams export gives us one — see
[corpus.md](corpus.md).

**"Not filtered at query time" is the whole deletion test.** Any design where the person's
data is still present and a filter hides it will be found, because the judges ask around
the edges. Whatever we do must change the thing we derived.

**"Keep answering" is half of the deletion score.** A system that deletes a person by
dropping every document they appear in will pass the first question and fail the next
three. The neighbouring decisions must survive.

**Deleting a person is not deleting a name.** The archive contains one person spelled two
ways and two people sharing a first name, both planted. A deletion implemented as string
replacement either misses half of a person or takes a bystander with them. See D19.

**Currency has two failure modes, not one.** Stale (true then, reversed later) and
never-true (wrong when recorded). A date sort cannot tell them apart, and the brief says so
explicitly — which is a strong hint that the graded set contains at least one of each.

**Attribution needs role-at-the-time.** Because people changed jobs, "who agreed" cannot
be answered from a person's current role. It has to be their role in the document where
they spoke.

**The archive is unflattering about RELEX, and the judges are RELEX.** The correct answer
is what the record says. An agent that hedges the vendor's failures is failing provenance
to be polite.

**The 15% is partly free.** Half of that slice is "an honest account of what it cannot
do". We know our limits already; writing them down well is cheap points and it is the
right thing to do regardless. The list lives in [roadmap.md](roadmap.md).

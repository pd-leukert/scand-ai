# Demo and judging prep

Submissions close **Sunday 12:00**. What we hand back is a URL the judges open and use
themselves, then a live question session where they check our citations by hand.

## Before we submit

- The Streamlit URL is reachable from outside our network, on a device that is not ours.
- It works for someone who has never seen it: the input is obvious and the first answer
  arrives without anyone explaining anything.
- Extraction has been run, the statements file is in place, and the backend has been
  restarted against it.
- Someone who did not build it has asked it three questions end to end.

## The order we show things

1. **A question with receipts.** Ask something about a decision. Show the answer, then
   expand a claim to the document, the location, and the quoted line. Let them pick the
   claim to expand.
2. **Suggestion versus commitment.** Ask about something that was proposed and never
   agreed. The valuable answer is "X proposed it on <date>; no agreement from the customer
   appears in the record" — with the citation for the proposal, and nothing invented for
   the agreement.
3. **Delete a person.** Let them pick. Run the deletion, show the receipt, then ask about
   that person — and then ask about a decision from the same meeting, which still answers.
   Say out loud that this is pseudonymisation and what that does and does not guarantee.
4. **The thing it does unasked.** *(TODO: pending the team's choice — see
   [roadmap.md](roadmap.md).)*
5. **What it cannot do.** Short, specific, unhedged. The honest-limits list from
   [roadmap.md](roadmap.md). This is scored.

## Answering the live questions

- **Citations are checked.** A citation that does not resolve to real text in a real
  document costs more than the claim was worth.
- **"The record does not say" is a correct answer** when the record does not say it. It is
  better than a plausible reconstruction, and this corpus is built to reward it.
- **When evidence conflicts, say so and cite both sides.** We have no currency signal, so
  we do not pick a winner. Presenting a conflict as a conflict is the honest move and it
  is the one our architecture supports.
- **Do not defend a gap.** Name it, point at the roadmap entry, move on.

## Questions to rehearse against

Once the documents are in hand, write a practice set covering each rubric slice —
including at least one question whose honest answer is "nobody ever agreed to that", and
one whose honest answer is "the record conflicts". The judges' set will be different; the
point is to find where we break, not to memorise answers.

"""Calls the answering LLM over an OpenAI-like REST API and turns its output into a
QueryResponse whose citations are guaranteed to resolve to real statements.

The model never gets to assert a citation directly. It tags claims with bracketed
markers and, at the end of its reply, lists the statement ids those markers refer to. The
backend then looks each id up in its own trusted copy of the reconciled file and builds
the citation from that — never from text the model produced. An id the model invents, or
mangles while copying it out of the record, simply resolves to nothing and is dropped. This
is what CLAUDE.md means by "if code cannot guarantee [a citation], it must emit no
citation rather than an approximate one" — see decisions.md D21. A statement's status, and
the ids that justify it, are copied the same way: the model reads a currency, it never
asserts one (D40).

The record is the reconciled file by default. ANSWER_SOURCE=statements answers from the flat
statements file instead, exactly as before D40: no status in the context, the prompt that says
currency is unknowable, and `status: null` on every citation.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator

import httpx

from .config import get_settings
from .schemas import Citation, QueryResponse
from .statements import Record, Statement, load_record, load_statements_record

DUMMY_STATEMENT_LIMIT = 5

CITATION_DELIMITER = "===CITATIONS==="

SYSTEM_PROMPT = f"""You are the answering agent for a rollout decision record.

You will be given the complete set of statements extracted from two years of project \
documents, grouped by topic, as a JSON object under STATEMENTS. It has two lists.

topics: every statement is in exactly one topic. A topic has a summary (one sentence, which \
may be missing), its relations, and its statements. Each statement has an id, a claim (one \
plain sentence saying what was stated), who said it (with their organisation), what kind of \
speech act it is (proposal, agreement, decision, report, question, objection), when it was \
said, and a status. There is no verbatim quote and no line location on a statement — the \
claim is the only record of what was said. A relation has a from, a to and a kind \
(supersedes, corrects, conflicts-with or answers), and names two statement ids in the same \
topic.

problems: places where a reader of the record would go wrong. Each has a kind (reversal, \
never-true, conflict or unanswered), the topic, the statement ids involved, and a note.

A status is one of current, stale, never-true, disputed or unresolved. It was worked out \
before you saw the record, from the relations, and it is the only information about currency \
there is.

Rules, no exceptions:
1. Answer only from the statements given. Never use outside knowledge. If nothing in the \
statements answers the question, say so plainly: "The record does not say."
2. A proposal or suggestion is not a commitment. Only report something as agreed or \
decided if a statement's speech_act says so (agreement or decision). The statements do \
not record who agreed to what beyond that — do not claim a specific person agreed unless \
their own statement is itself the agreement or decision.
3. Use each person's organisation as recorded on the statement you are citing, not any \
organisation they hold elsewhere in the record.
4. Use the status, and never judge currency yourself. Do not infer which statement is \
current from dates or from the order statements appear in. A statement that is current may \
be reported as what the record says. An unresolved statement is a proposal or question \
nobody answered: say so, and do not report it as agreed.
5. A stale statement was true when it was said and replaced later. A never-true statement was \
wrong when it was recorded. Never report either as fact. Report it as what the record once \
said, say which of the two it is, and name and cite the statements whose relations \
superseded or corrected it. Do not leave it out: an answer about how something changed cites \
both the old statement and what replaced it.
6. If two statements are disputed, report the conflict and cite both. Do not decide which \
one holds. If two statements seem to disagree and no relation says so, say what each says \
and do not decide either.
7. If the question touches a topic that has an entry under problems, say what the problem \
is and cite the statements it names.
8. Cite every factual claim. Mark it inline with a bracketed number, e.g. [1], in the \
order statements are first used, starting at 1. Reuse the same number for repeated use of \
the same statement. Cite statements, never a summary or a note: those point at statements, \
they are not evidence.
9. After the answer, on its own line, write exactly `{CITATION_DELIMITER}` followed by a \
JSON array of the statement ids the markers refer to, in marker order, e.g. \
["s4", "s11"]. If you used no markers, write an empty array []. Use only ids that appear in \
the statements you were given — never invent one.
"""

# For ANSWER_SOURCE=statements: the prompt as it was before D40. Nothing was reconciled, so the
# model is told currency is unknowable rather than shown a status that no pass produced.
STATEMENTS_ONLY_PROMPT = f"""You are the answering agent for a rollout decision record.

You will be given the complete set of statements extracted from a year of project \
documents, as a JSON array under STATEMENTS, grouped by document. Each entry is one \
document, and has the document's id and date once, plus a list of its statements. Each \
statement has an id, a claim (one plain sentence saying what was stated), who said it (with \
their organisation), what kind of speech act it is (proposal, agreement, decision, report, \
question, objection), and when it was said. There is no verbatim quote and no line location \
on a statement — the claim is the only record of what was said.

Rules, no exceptions:
1. Answer only from the statements given. Never use outside knowledge. If nothing in the \
statements answers the question, say so plainly: "The record does not say."
2. A proposal or suggestion is not a commitment. Only report something as agreed or \
decided if a statement's speech_act says so (agreement or decision). The statements do \
not record who agreed to what beyond that — do not claim a specific person agreed unless \
their own statement is itself the agreement or decision.
3. Use each person's organisation as recorded on the statement you are citing, not any \
organisation they hold elsewhere in the record.
4. If two statements conflict, report the conflict and cite both. Do not decide which one \
is current — you have no way to know that, and guessing is worse than saying so.
5. Cite every factual claim. Mark it inline with a bracketed number, e.g. [1], in the \
order statements are first used, starting at 1. Reuse the same number for repeated use of \
the same statement.
6. After the answer, on its own line, write exactly `{CITATION_DELIMITER}` followed by a \
JSON array of the statement ids the markers refer to, in marker order, e.g. \
["s4", "s11"]. If you used no markers, write an empty array []. Use only ids that appear in \
the statements you were given — never invent one.
"""


def _aliases(record: Record) -> dict[str, str]:
    """A short id for every statement, by real id: s1, s2, … in the record's own order.

    The model is shown these and never a real id. A real id is a document path and a position
    — about twenty tokens, repeated in every relation, problem and summary that names the
    statement, which measured at over a quarter of the reconciled payload (D44). It is the same
    device reconcile.py uses on its side (S1, S2, …), and for the same reason: an alias the
    model returns that we did not hand out resolves to nothing and is dropped, so the citation
    trust boundary is exactly where it was (D21). Derived from the record on each call, so it is
    stored nowhere a deletion would have to reach (CLAUDE.md rule 4).
    """
    return {statement_id: f"s{number}" for number, statement_id in enumerate(record.statements, 1)}


def _statement_view(statement: Statement, alias: str, *, with_status: bool) -> dict:
    """What the model is shown of one statement. Nothing document-level (the id it already
    has says which document, and the date is the statement's own) and nothing the file does
    not carry (D37)."""
    view = {
        "id": alias,
        "claim": statement.claim,
        "actor": {"name": statement.actor.name, "organization": statement.actor.organization},
        "speech_act": statement.speech_act,
        # Dates only: extraction writes a day, and a datetime would add a time of day to every
        # statement that nobody recorded.
        "statement_date": statement.statement_date.date().isoformat(),
    }
    if with_status:
        view["status"] = statement.status
    return view


def _aliased(text: str, aliases: dict[str, str], ids: list[str]) -> str:
    """A note with the real ids it names swapped for their aliases. The templated problem notes
    write ids into their sentence, and a real id left in one would be a long id the model could
    cite and we would then drop.

    Two separate guards, each with its own test. Longest first, because one id can be the tail
    of another ("a/x#1" inside "b/a/x#1") and replacing the short one first leaves the long one
    as "b" + an alias. And never in front of a digit, because "doc#1" is the start of "doc#12":
    a note that names #12 without listing it must not come out as an alias followed by "2"."""
    for statement_id in sorted(ids, key=len, reverse=True):
        text = re.sub(re.escape(statement_id) + r"(?!\d)", aliases[statement_id], text)
    return text


def _reconciled_payload(record: Record, aliases: dict[str, str]) -> dict:
    return {
        "topics": [
            {
                "topic": topic.topic,
                "summary": (
                    {
                        "text": topic.summary.text,
                        "statements": [aliases[i] for i in topic.summary.statements],
                    }
                    if topic.summary
                    else None
                ),
                "relations": [
                    {"from": aliases[r.source], "to": aliases[r.to], "kind": r.kind}
                    for r in topic.relations
                ],
                "statements": [
                    _statement_view(s, aliases[s.id], with_status=True) for s in topic.statements
                ],
            }
            for topic in record.topics
        ],
        "problems": [
            {
                "kind": problem.kind,
                "topic": problem.topic,
                "statements": [aliases[i] for i in problem.statements],
                "note": _aliased(problem.note, aliases, problem.statements),
            }
            for problem in record.problems
        ],
    }


def _grouped_payload(record: Record, aliases: dict[str, str]) -> list[dict]:
    """The statements regrouped by document for the model's context: document_id and
    document_date appear once per document instead of once per statement — the same
    reduction the statements file itself uses on disk (docs/decisions.md D36), reapplied
    here because this payload is what actually gets rebuilt and resent on every question
    (D2), which is where the token count actually matters. No status: nothing was reconciled,
    so every statement's default of "current" is one nobody worked out."""
    groups: dict[str, dict] = {}
    for statement in record.statements.values():
        group = groups.setdefault(
            statement.document_id,
            {
                "document_id": statement.document_id,
                "document_date": statement.document_date.isoformat(),
                "statements": [],
            },
        )
        group["statements"].append(
            _statement_view(statement, aliases[statement.id], with_status=False)
        )
    return list(groups.values())


def _build_messages(question: str, record: Record) -> list[dict[str, str]]:
    aliases = _aliases(record)
    if record.reconciled:
        prompt, payload = SYSTEM_PROMPT, _reconciled_payload(record, aliases)
    else:
        prompt, payload = STATEMENTS_ONLY_PROMPT, _grouped_payload(record, aliases)
    # The record goes before the question so that the long half of the prompt is a stable
    # prefix: Ollama caches it, and only the question is processed again on the next one.
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"STATEMENTS:\n{json.dumps(payload)}\n\nQUESTION:\n{question}"},
    ]


def _split_response(raw_text: str) -> tuple[str, list[str]]:
    if CITATION_DELIMITER not in raw_text:
        return raw_text, []
    prose, _, tail = raw_text.partition(CITATION_DELIMITER)
    try:
        ids = json.loads(tail.strip())
    except json.JSONDecodeError:
        return prose, []
    if not isinstance(ids, list):
        return prose, []
    return prose, [str(alias) for alias in ids]


def _resolve_citations(cited: list[str], record: Record) -> list[Citation]:
    """The citations for what the model cited. It cites the aliases it was shown (_aliases);
    each is looked up here and anything that is not one we handed out is dropped."""
    by_alias = {alias: statement_id for statement_id, alias in _aliases(record).items()}
    citations = []
    for marker, alias in enumerate(cited, start=1):
        statement = record.statements.get(by_alias.get(alias, ""))
        if statement is None:
            continue
        citations.append(
            Citation(
                marker=marker,
                statement_id=statement.id,
                document_id=statement.document_id,
                claim=statement.claim,
                actor=statement.actor,
                speech_act=statement.speech_act,
                statement_date=statement.statement_date,
                document_date=statement.document_date,
                status=statement.status if record.reconciled else None,
                status_receipts=record.receipts.get(statement.id, []),
            )
        )
    return citations


# Plain JSON of this record tokenises at roughly this many characters a token. Prose is about
# four; the ids, field names and punctuation between the words drag it down. Measured on
# qwen3:0.6b against the four-document record: 76k characters came to 29,356 prompt tokens, or
# 2.59. Rounded down, not up, on purpose — a low divisor overestimates the tokens, and the cost
# of overestimating is a question refused that would just have fitted, while the cost of
# underestimating is an answer drawn from whichever part of the record survived truncation.
# Another model's tokenizer will differ; this is the order of magnitude, not a promise.
JSON_CHARS_PER_TOKEN = 2.5


def context_shortfall(question: str) -> tuple[int, int] | None:
    """(estimated prompt tokens, configured context) if the prompt will not fit, else None.

    Ollama truncates a prompt over the served context silently, and its OpenAI-compatible
    endpoint has no per-request `num_ctx` — the server's OLLAMA_CONTEXT_LENGTH decides. So the
    backend cannot make the window bigger from here; it can only refuse to answer from a record
    the model would only partly see. LLM_NUM_CTX is what the server is configured to serve, and
    leaving it unset turns the guard off. See D43.
    """
    settings = get_settings()
    if not settings.llm_num_ctx:
        return None
    chars = sum(len(message["content"]) for message in _build_messages(question, _load_record()))
    tokens = round(chars / JSON_CHARS_PER_TOKEN)
    return (tokens, settings.llm_num_ctx) if tokens > settings.llm_num_ctx else None


def _load_record() -> Record:
    settings = get_settings()
    if settings.answer_source == "statements":
        return load_statements_record(settings.statements_file)
    return load_record(settings.reconciled_file)


def _dummy_answer(record: Record) -> tuple[str, list[str]]:
    """A canned answer for exercising the /query wire format (SSE framing, inline markers,
    citation resolution) without a configured LLM. Built entirely from statements already
    loaded from the trusted file — DUMMY_LLM skips the model call, never the citation trust
    boundary, so this still can't emit a citation that isn't real. See module docstring."""
    picked = list(record.statements.values())[:DUMMY_STATEMENT_LIMIT]
    if not picked:
        return "The record is empty; there is nothing to cite.", []
    sentences = [
        f"{statement.actor.name} ({statement.actor.organization}) "
        f"{statement.speech_act} on {statement.document_date}: "
        f"{statement.claim} [{marker}]."
        for marker, statement in enumerate(picked, start=1)
    ]
    prose = (
        "This is a dummy answer for testing — DUMMY_LLM is set, so no model was called. "
        + " ".join(sentences)
    )
    aliases = _aliases(record)
    return prose, [aliases[statement.id] for statement in picked]


async def _stream_dummy_answer(record: Record) -> AsyncIterator[bytes]:
    delay_seconds = get_settings().dummy_llm_delay_seconds
    prose, cited = _dummy_answer(record)
    for token in re.findall(r"\S+\s*", prose):
        yield _sse("token", {"text": token})
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
    citations = _resolve_citations(cited, record)
    yield _sse("citations", {"citations": [c.model_dump(mode="json") for c in citations]})
    yield _sse("done", {})


def _request_payload(question: str, record: Record, *, stream: bool) -> dict:
    settings = get_settings()
    return {
        "model": settings.llm_model,
        "messages": _build_messages(question, record),
        "stream": stream,
        # Answering is picking and paraphrasing a citation, not solving a novel problem — a
        # thinking model spends real wall-clock time reasoning before it ever emits the
        # answer. docs/qwen_3.8_quickstart.md's documented way to fully disable it is
        # chat_template_kwargs.enable_thinking, not "reasoning_effort" (that dial only goes
        # down to "low" for this model family, never off) and not extraction's native-API
        # "think" field — see D34. Left unverified against the real 27B deployment model;
        # it's a no-op against the dev-default qwen3:0.6b, which doesn't speak this template.
        "chat_template_kwargs": {"enable_thinking": False},
    }


def _headers() -> dict[str, str]:
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    return headers


async def answer_question(question: str) -> QueryResponse:
    settings = get_settings()
    record = _load_record()
    if settings.dummy_llm:
        prose, cited = _dummy_answer(record)
        return QueryResponse(answer=prose, citations=_resolve_citations(cited, record))
    payload = _request_payload(question, record, stream=False)
    url = f"{settings.llm_base_url}/chat/completions"

    async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
        response = await client.post(url, json=payload, headers=_headers())
        response.raise_for_status()
        body = response.json()

    raw_text = body["choices"][0]["message"]["content"]
    prose, cited = _split_response(raw_text)
    citations = _resolve_citations(cited, record)
    return QueryResponse(answer=prose.strip(), citations=citations)


def _sse(event: str, payload: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode()


async def stream_answer_question(question: str) -> AsyncIterator[bytes]:
    """Stream the prose answer live; hold citations back until the whole reply is in and
    validated, so nothing unverified reaches the client. See module docstring."""
    settings = get_settings()
    record = _load_record()
    if settings.dummy_llm:
        async for chunk in _stream_dummy_answer(record):
            yield chunk
        return
    payload = _request_payload(question, record, stream=True)
    url = f"{settings.llm_base_url}/chat/completions"

    buffer = ""
    flushed = 0
    delimiter_seen = False
    safety_margin = len(CITATION_DELIMITER) - 1

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
            async with client.stream("POST", url, json=payload, headers=_headers()) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if not delta:
                        continue
                    buffer += delta

                    if not delimiter_seen and CITATION_DELIMITER in buffer:
                        delimiter_seen = True
                        idx = buffer.index(CITATION_DELIMITER)
                        if idx > flushed:
                            yield _sse("token", {"text": buffer[flushed:idx]})
                        flushed = idx
                        continue
                    if delimiter_seen:
                        continue

                    safe_upto = len(buffer) - safety_margin
                    if safe_upto > flushed:
                        yield _sse("token", {"text": buffer[flushed:safe_upto]})
                        flushed = safe_upto
    except httpx.HTTPError as exc:
        # An exception here would otherwise kill the ASGI response mid-chunk: headers and
        # some body already sent, then nothing — the client sees a broken chunked stream
        # ("Response ended prematurely"), not the message on this exception. Ending the SSE
        # stream on our own terms, with an honest error event, is what the frontend already
        # has a display for.
        yield _sse("error", {"message": f"The model did not answer: {exc}"})
        return

    if not delimiter_seen and len(buffer) > flushed:
        yield _sse("token", {"text": buffer[flushed:]})

    _, cited = _split_response(buffer)
    citations = _resolve_citations(cited, record)
    yield _sse("citations", {"citations": [c.model_dump(mode="json") for c in citations]})
    yield _sse("done", {})

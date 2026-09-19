"""Calls the answering LLM over an OpenAI-like REST API and turns its output into a
QueryResponse whose citations are guaranteed to resolve to real statements.

The model never gets to assert a citation directly. It tags claims with bracketed
markers and, at the end of its reply, lists the statement ids those markers refer to. The
backend then looks each id up in its own trusted copy of the statements file and builds
the citation from that — never from text the model produced. An id the model invents, or
mangles while decoding the base64 payload, simply resolves to nothing and is dropped. This
is what CLAUDE.md means by "if code cannot guarantee [a citation], it must emit no
citation rather than an approximate one" — see decisions.md D21.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
from collections.abc import AsyncIterator

import httpx

from .config import get_settings
from .schemas import Citation, QueryResponse
from .statements import Statement, load_statements

DUMMY_STATEMENT_LIMIT = 5

CITATION_DELIMITER = "===CITATIONS==="

SYSTEM_PROMPT = f"""You are the answering agent for a rollout decision record.

You will be given the complete set of statements extracted from a year of project \
documents, base64-encoded under STATEMENTS_B64 as a JSON array grouped by document. Decode \
it before answering. Each entry is one document, and has the document's id and date once, \
plus a list of its statements. Each statement has an id, a claim (one plain sentence \
saying what was stated), who said it (with their organisation), what kind of speech act it \
is (proposal, agreement, decision, report, question, objection), and when it was said. \
There is no verbatim quote and no line location on a statement — the claim is the only \
record of what was said.

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
["stmt-004", "stmt-011"]. If you used no markers, write an empty array []. Use only ids \
that appear in the statements you were given — never invent one.
"""


def _grouped_payload(statements: dict[str, Statement]) -> list[dict]:
    """The statements regrouped by document for the model's context: document_id and
    document_date appear once per document instead of once per statement — the same
    reduction the statements file itself uses on disk (docs/decisions.md D36), reapplied
    here because this payload is what actually gets rebuilt and resent on every question
    (D2), which is where the token count actually matters."""
    groups: dict[str, dict] = {}
    for statement in statements.values():
        dumped = statement.model_dump(mode="json")
        document_id = dumped.pop("document_id")
        document_date = dumped.pop("document_date")
        group = groups.setdefault(
            document_id,
            {"document_id": document_id, "document_date": document_date, "statements": []},
        )
        group["statements"].append(dumped)
    return list(groups.values())


def _build_messages(question: str, statements: dict[str, Statement]) -> list[dict[str, str]]:
    payload = json.dumps(_grouped_payload(statements))
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"STATEMENTS_B64:\n{encoded}\n\nQUESTION:\n{question}"},
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
    return prose, [str(statement_id) for statement_id in ids]


def _resolve_citations(
    statement_ids: list[str], statements: dict[str, Statement]
) -> list[Citation]:
    citations = []
    for marker, statement_id in enumerate(statement_ids, start=1):
        statement = statements.get(statement_id)
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
            )
        )
    return citations


def _dummy_answer(statements: dict[str, Statement]) -> tuple[str, list[str]]:
    """A canned answer for exercising the /query wire format (SSE framing, inline markers,
    citation resolution) without a configured LLM. Built entirely from statements already
    loaded from the trusted file — DUMMY_LLM skips the model call, never the citation trust
    boundary, so this still can't emit a citation that isn't real. See module docstring."""
    picked = list(statements.values())[:DUMMY_STATEMENT_LIMIT]
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
    return prose, [statement.id for statement in picked]


async def _stream_dummy_answer(statements: dict[str, Statement]) -> AsyncIterator[bytes]:
    delay_seconds = get_settings().dummy_llm_delay_seconds
    prose, statement_ids = _dummy_answer(statements)
    for token in re.findall(r"\S+\s*", prose):
        yield _sse("token", {"text": token})
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
    citations = _resolve_citations(statement_ids, statements)
    yield _sse("citations", {"citations": [c.model_dump(mode="json") for c in citations]})
    yield _sse("done", {})


def _request_payload(question: str, statements: dict[str, Statement], *, stream: bool) -> dict:
    settings = get_settings()
    return {
        "model": settings.llm_model,
        "messages": _build_messages(question, statements),
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
    statements = load_statements(settings.statements_file)
    if settings.dummy_llm:
        prose, statement_ids = _dummy_answer(statements)
        return QueryResponse(answer=prose, citations=_resolve_citations(statement_ids, statements))
    payload = _request_payload(question, statements, stream=False)
    url = f"{settings.llm_base_url}/chat/completions"

    async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
        response = await client.post(url, json=payload, headers=_headers())
        response.raise_for_status()
        body = response.json()

    raw_text = body["choices"][0]["message"]["content"]
    prose, statement_ids = _split_response(raw_text)
    citations = _resolve_citations(statement_ids, statements)
    return QueryResponse(answer=prose.strip(), citations=citations)


def _sse(event: str, payload: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode()


async def stream_answer_question(question: str) -> AsyncIterator[bytes]:
    """Stream the prose answer live; hold citations back until the whole reply is in and
    validated, so nothing unverified reaches the client. See module docstring."""
    settings = get_settings()
    statements = load_statements(settings.statements_file)
    if settings.dummy_llm:
        async for chunk in _stream_dummy_answer(statements):
            yield chunk
        return
    payload = _request_payload(question, statements, stream=True)
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

    _, statement_ids = _split_response(buffer)
    citations = _resolve_citations(statement_ids, statements)
    yield _sse("citations", {"citations": [c.model_dump(mode="json") for c in citations]})
    yield _sse("done", {})

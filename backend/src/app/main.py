import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .config import get_settings
from .llm_client import answer_question, context_shortfall, stream_answer_question
from .schemas import QueryRequest, QueryResponse

# A bad setting stops the container here, with the reason in its log, not on the first question
# behind a healthy healthcheck.
get_settings()

app = FastAPI(
    title="scand-ai backend",
    version="0.1.0",
)


@app.post("/query", response_model=None)
async def query(request: QueryRequest) -> QueryResponse | StreamingResponse:
    """Answer a question from the reconciled file only, with verified citations."""
    # Checked here rather than inside the generator: once a StreamingResponse has started there
    # is no status code left to set, and a half-answer from a truncated record is the one thing
    # this must not do. See D34.
    if shortfall := context_shortfall(request.question):
        tokens, num_ctx = shortfall
        raise HTTPException(
            status_code=413,
            detail=(
                f"The record comes to about {tokens:,} tokens and this model is configured to "
                f"serve {num_ctx:,} (LLM_NUM_CTX). Ollama truncates a prompt over its context "
                "without saying so, and an answer drawn from whichever part survived is not an "
                "answer from the record. Raise OLLAMA_CONTEXT_LENGTH and LLM_NUM_CTX together, "
                "or narrow the record."
            ),
        )
    if request.stream:
        return StreamingResponse(
            stream_answer_question(request.question),
            media_type="text/event-stream",
        )
    try:
        return await answer_question(request.question)
    except httpx.TimeoutException as timeout:
        # The whole record is processed as prompt before a single token comes back, so a slow
        # box times out rather than answers. Saying that is useful; a 500 and a traceback in
        # the backend log is not. See D34.
        waited = get_settings().llm_timeout_seconds
        raise HTTPException(
            status_code=504,
            detail=(
                f"The model did not answer within LLM_TIMEOUT ({waited:.0f}s). "
                "The whole record is processed as prompt before the first token, so this is the "
                "record's size against this machine's speed, not a hung request. Raise "
                "LLM_TIMEOUT, or answer from a smaller record."
            ),
        ) from timeout


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

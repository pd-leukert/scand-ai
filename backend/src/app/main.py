from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from .config import get_settings
from .llm_client import answer_question, stream_answer_question
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
    if request.stream:
        return StreamingResponse(
            stream_answer_question(request.question),
            media_type="text/event-stream",
        )
    return await answer_question(request.question)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

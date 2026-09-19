from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .config import statements_file_path
from .delete import delete_from_file
from .llm_client import answer_question, stream_answer_question
from .schemas import DeleteRequest, DeleteResponse, QueryRequest, QueryResponse

app = FastAPI(
    title="scand-ai backend",
    version="0.1.0",
)


@app.post("/query", response_model=None)
async def query(request: QueryRequest) -> QueryResponse | StreamingResponse:
    """Answer a question from the statements file only, with verified citations."""
    if request.stream:
        return StreamingResponse(
            stream_answer_question(request.question),
            media_type="text/event-stream",
        )
    return await answer_question(request.question)


@app.post("/delete", response_model=DeleteResponse)
def delete(request: DeleteRequest) -> DeleteResponse:
    """Delete one person from the statements file and return the receipt.

    The file is rewritten, not filtered at query time (CLAUDE.md rule 3), and the answering path
    re-reads it on every request (D44), so the next answer is already without them. A request
    that matches nobody comes back with `deleted: null` and an untouched file — that is an
    answer, not an error. Sync on purpose: the work is file I/O in a threadpool, not the event
    loop, and delete_from_file serialises concurrent calls.
    """
    path = Path(statements_file_path())
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"There is no statements file at {path}.")
    return DeleteResponse.model_validate(delete_from_file(path, request.name))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

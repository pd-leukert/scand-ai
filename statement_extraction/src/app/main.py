import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

STARTUP_WAIT_SECONDS = 60


async def _exit_after_wait() -> None:
    await asyncio.sleep(STARTUP_WAIT_SECONDS)
    # A signal would make uvicorn re-raise it and exit non-zero; this is a clean exit 0.
    os._exit(0)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    task = asyncio.create_task(_exit_after_wait())
    yield
    task.cancel()


app = FastAPI(
    title="scand-ai statement extraction",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello, world!"}

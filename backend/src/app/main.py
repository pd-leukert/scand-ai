from fastapi import FastAPI

app = FastAPI(
    title="scand-ai backend",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello, world!"}

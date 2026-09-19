# Build context is the repository root: the uv workspace keeps one lockfile, and it lives
# there. See docs/decisions.md D11.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Manifests first, so editing our code does not reinstall the dependencies. Every workspace
# member has to be present for uv to resolve against the committed lockfile.
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/
COPY frontend/pyproject.toml frontend/
COPY statement_extraction/pyproject.toml statement_extraction/
RUN uv sync --locked --package backend --no-install-workspace

COPY backend/ backend/

# The two derived files, and the only things the answering path reads. Both stay on the
# volume compose mounts read-only; extraction is the only writer. config.py reads them as
# STATEMENTS_FILE_PATH and RECONCILED_FILE_PATH — these names have to match what extraction's
# Dockerfile sets, or the backend silently falls back to the bundled mock files. ANSWER_SOURCE
# picks which one it answers from, and defaults to the reconciled file. See D28 and D40.
ENV STATEMENTS_FILE_PATH=/data/statements.json \
    RECONCILED_FILE_PATH=/data/reconciled.json

WORKDIR /app/backend
EXPOSE 8000

# The command from backend/README.md, minus dev reload.
CMD ["uv", "run", "--frozen", "fastapi", "run"]

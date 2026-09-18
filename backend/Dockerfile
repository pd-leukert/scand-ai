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

# The statements file the answering path reads, and the only thing it reads. Mounted
# read-only by compose; extraction is the only writer.
ENV STATEMENTS_PATH=/data/statements.json

WORKDIR /app/backend
EXPOSE 8000

# The command from backend/README.md, minus dev reload.
CMD ["uv", "run", "--frozen", "fastapi", "run"]

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
RUN uv sync --locked --package statement-extraction --no-install-workspace

COPY statement_extraction/ statement_extraction/

# The archive is baked into the image, so the job needs nothing mounted. See D18.
COPY input/ input/

# Where this job writes the statements file. It is the only writer. Same variable name the
# backend reads (config.py) — one name for the one artifact, not two that have to agree.
ENV STATEMENTS_FILE_PATH=/data/statements.json

# The second file, written after the first by the reconciliation pass (D31). The backend reads
# this one, under the same variable name.
ENV RECONCILED_FILE_PATH=/data/reconciled.json

WORKDIR /app/statement_extraction

# A job, not a server: run the extraction script and exit. See D28.
CMD ["uv", "run", "--frozen", "python", "-m", "src.app.extract"]

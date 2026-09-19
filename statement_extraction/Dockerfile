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

# Where this job writes the statements file. It is the only writer.
ENV STATEMENTS_PATH=/data/statements.jsonl

WORKDIR /app/statement_extraction
EXPOSE 8000

# The command from statement_extraction/README.md, minus dev reload. This container is a
# job: it is expected to exit 0, and compose holds the other two until it does.
CMD ["uv", "run", "--frozen", "fastapi", "run"]

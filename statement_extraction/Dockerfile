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

# The corpus, baked into the image per docs/decisions.md D18 — .dockerignore does not
# exclude it, so this is the one line D18 calls for.
COPY input/ input/

WORKDIR /app/statement_extraction

# This container is a job: pipeline.run exits 0 once every document is parsed and
# annotated, and compose holds backend/frontend until it does. See docs/decisions.md D12.
CMD ["uv", "run", "--frozen", "python", "-m", "pipeline.run", "--out-dir", "/data"]

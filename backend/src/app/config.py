"""Answering-path configuration. Values only — see CLAUDE.md: the model is a
configuration value, never a hardcoded name."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    llm_base_url: str | None
    llm_model: str | None
    llm_api_key: str | None
    # What the Ollama server is configured to serve, not something we can ask for per request:
    # the OpenAI-compatible endpoint has no num_ctx. Unset turns the size guard off. See D43.
    llm_num_ctx: int | None
    # Seconds to wait on one answer. Prompt processing is linear in the size of the record, so
    # the laptop stack needs far longer than a GPU does. See D43.
    llm_timeout_seconds: float
    answer_source: Literal["reconciled", "statements"]
    statements_file: str
    reconciled_file: str
    dummy_llm: bool
    dummy_llm_delay_seconds: float


@lru_cache
def get_settings() -> Settings:
    dummy_llm = os.environ.get("DUMMY_LLM", "").strip().lower() in ("1", "true", "yes")
    base_url = os.environ.get("LLM_BASE_URL")
    model = os.environ.get("LLM_MODEL")
    if not dummy_llm:
        if not base_url:
            raise ConfigError("LLM_BASE_URL is not set")
        if not model:
            raise ConfigError("LLM_MODEL is not set")
    answer_source = os.environ.get("ANSWER_SOURCE", "reconciled").strip().lower()
    if answer_source not in ("reconciled", "statements"):
        raise ConfigError(
            f"ANSWER_SOURCE must be 'reconciled' or 'statements', not {answer_source!r}"
        )
    raw_num_ctx = os.environ.get("LLM_NUM_CTX", "").strip()
    num_ctx = int(raw_num_ctx) if raw_num_ctx else None
    if num_ctx is not None and num_ctx <= 0:
        raise ConfigError(f"LLM_NUM_CTX must be a positive number of tokens, not {raw_num_ctx!r}")
    data = Path(__file__).parent / "data"
    return Settings(
        llm_base_url=base_url.rstrip("/") if base_url else None,
        llm_model=model,
        llm_api_key=os.environ.get("LLM_API_KEY"),
        llm_num_ctx=num_ctx,
        llm_timeout_seconds=float(os.environ.get("LLM_TIMEOUT", "120")),
        answer_source=answer_source,
        statements_file=os.environ.get("STATEMENTS_FILE_PATH", str(data / "mock_statements.json")),
        reconciled_file=os.environ.get("RECONCILED_FILE_PATH", str(data / "mock_reconciled.json")),
        dummy_llm=dummy_llm,
        dummy_llm_delay_seconds=float(os.environ.get("DUMMY_LLM_DELAY_SECONDS", "0.05")),
    )

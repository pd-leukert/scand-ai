"""Answering-path configuration. Values only — see CLAUDE.md: the model is a
configuration value, never a hardcoded name."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


class ConfigError(RuntimeError):
    pass


# The statements file the answering path reads and deletion rewrites. Read on its own by
# statements_file_path(), so the deletion command works without the model settings below.
DEFAULT_STATEMENTS_FILE = Path(__file__).parent / "data" / "mock_statements.json"


def statements_file_path() -> str:
    return os.environ.get("STATEMENTS_FILE_PATH", str(DEFAULT_STATEMENTS_FILE))


@dataclass(frozen=True)
class Settings:
    llm_base_url: str | None
    llm_model: str | None
    llm_api_key: str | None
    llm_timeout: float
    statements_file: str
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
    return Settings(
        llm_base_url=base_url.rstrip("/") if base_url else None,
        llm_model=model,
        llm_api_key=os.environ.get("LLM_API_KEY"),
        llm_timeout=float(os.environ.get("LLM_TIMEOUT", "600")),
        statements_file=statements_file_path(),
        dummy_llm=dummy_llm,
        dummy_llm_delay_seconds=float(os.environ.get("DUMMY_LLM_DELAY_SECONDS", "0.05")),
    )

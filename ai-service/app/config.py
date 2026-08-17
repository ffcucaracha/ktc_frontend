from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMSettings:
    mode: str
    base_url: str
    model: str
    api_key: str | None
    timeout_seconds: float
    temperature: float
    rag_enabled: bool = False


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_llm_settings() -> LLMSettings:
    return LLMSettings(
        mode=os.getenv("AI_LLM_MODE", "disabled").strip().lower(),
        base_url=os.getenv("AI_LLM_BASE_URL", "http://host.docker.internal:11434/v1").rstrip("/"),
        model=os.getenv("AI_LLM_MODEL", "qwen2.5:7b-instruct"),
        api_key=os.getenv("AI_LLM_API_KEY") or None,
        timeout_seconds=float(os.getenv("AI_LLM_TIMEOUT_SECONDS", "30")),
        temperature=float(os.getenv("AI_LLM_TEMPERATURE", "0.2")),
        rag_enabled=_env_bool("RAG_ENABLED", False),
    )

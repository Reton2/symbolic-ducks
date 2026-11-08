from __future__ import annotations

import os

from pydantic import BaseModel


class AutoformalizerConfig(BaseModel):
    """Configuration contract for deep autoformalization pipeline."""

    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    max_concurrency: int = 16
    chunk_size: int = 30
    temperature: float = 0.0
    log_level: str = "INFO"
    cache_dir: str = ".cache/autoformalisation"
    enable_cache: bool = True

    @classmethod
    def from_env(cls) -> AutoformalizerConfig:
        return cls(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
            max_concurrency=int(os.getenv("MAX_CONCURRENCY", "16")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "30")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            cache_dir=os.getenv(
                "AUTOFORMALISATION_CACHE_DIR",
                os.getenv("CACHE_DIR", ".cache/autoformalisation"),
            ),
            enable_cache=os.getenv("ENABLE_CACHE", "true").lower()
            in ("true", "1", "yes"),
        )

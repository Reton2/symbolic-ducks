from __future__ import annotations

import os

from pydantic import BaseModel, Field


class AutoformalizerConfig(BaseModel):
    """Configuration contract for deep autoformalization pipeline."""

    model: str = Field(...)
    base_url: str = Field(...)
    api_key: str = Field(...)
    max_concurrency: int = Field(default=16)
    max_repair_attempts: int = Field(default=3)
    chunk_size: int = Field(default=30)
    temperature: float = Field(default=0.0)
    log_level: str = Field(default="INFO")
    cache_dir: str = Field(default=".cache/autoformalisation")
    enable_cache: bool = Field(default=True)

    @classmethod
    def from_env(cls) -> AutoformalizerConfig:
        return cls(
            model=os.getenv("LLM_MODEL") or "gpt-4o-mini",
            base_url=os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1",
            api_key=os.getenv("LLM_API_KEY") or "",
        )

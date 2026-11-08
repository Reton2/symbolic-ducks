from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path

from app.schemas import (
    AutonomousPolicyGraph,
)

logger = logging.getLogger(__name__)


class PolicyGraphCache:
    """Manages disk-based persistent caching for AutonomousPolicyGraph models keyed by raw text hash."""

    def __init__(
        self,
        cache_dir: str | Path = ".cache/autoformalisation",
        enabled: bool = True,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled

    @staticmethod
    def compute_hash(raw_text: str) -> str:
        """Compute SHA-256 hex digest of raw text."""
        return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    def get_cache_path(self, raw_text: str) -> Path:
        """Resolve filesystem path for a cached graph corresponding to raw_text."""
        return self.cache_dir / f"{self.compute_hash(raw_text)}.json"

    def get(self, raw_text: str) -> AutonomousPolicyGraph | None:
        """Retrieve and validate cached AutonomousPolicyGraph if file exists and is valid."""
        if not self.enabled:
            return None

        path = self.get_cache_path(raw_text)
        if not path.is_file():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            graph = AutonomousPolicyGraph.model_validate_json(content)
            logger.info(
                "[Cache Hit] Loaded persistent policy graph from %s (hash=%s)",
                path,
                self.compute_hash(raw_text)[:12],
            )
            return graph
        except Exception as err:
            logger.warning(
                "[Cache Corrupt] Failed to load cached graph from %s: %s (will recompute)",
                path,
                err,
            )
            return None

    def put(self, raw_text: str, graph: AutonomousPolicyGraph) -> Path | None:
        """Atomically persist AutonomousPolicyGraph to disk keyed by raw_text hash."""
        if not self.enabled:
            return None

        path = self.get_cache_path(raw_text)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
            tmp_path.write_text(graph.model_dump_json(indent=2), encoding="utf-8")
            tmp_path.replace(path)
            logger.info(
                "[Cache Saved] Persisted policy graph to %s (hash=%s)",
                path,
                self.compute_hash(raw_text)[:12],
            )
            return path
        except Exception as err:
            logger.warning(
                "[Cache Error] Failed to persist graph to %s: %s",
                path,
                err,
            )
            return None

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.schemas import AutonomousPolicyGraph

logger = logging.getLogger(__name__)


class PolicyGraphCache:
    """Manages disk-based persistent caching for AutonomousPolicyGraph models."""

    def __init__(
        self,
        cache_dir: str | Path = ".cache/autoformalisation",
        enabled: bool = True,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled

    @staticmethod
    def compute_hash(raw_text: str) -> str:
        """Computes SHA-256 hex digest of raw text."""
        return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    def get_cache_path(self, raw_text: str) -> Path:
        """Resolves filesystem path for a cached graph corresponding to raw_text."""
        return self.cache_dir / f"{self.compute_hash(raw_text)}.json"

    def get(self, raw_text: str) -> AutonomousPolicyGraph | None:
        """Retrieves and validates cached AutonomousPolicyGraph if file exists and is valid."""
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
        """Atomically persists AutonomousPolicyGraph to disk keyed by raw_text hash."""
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
            logger.warning("[Cache Error] Failed to persist graph to %s: %s", path, err)
            return None


class IntermediateStateStore:
    """Persists intermediate pipeline stages to disk keyed by text hash."""

    def __init__(self, cache_dir: str | Path = ".cache/autoformalisation") -> None:
        self.base_path = Path(cache_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_doc_dir(self, raw_text: str) -> Path:
        """Returns dedicated subfolder for the document hash."""
        doc_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16]
        doc_dir = self.base_path / f"policy_{doc_hash}"
        doc_dir.mkdir(parents=True, exist_ok=True)
        return doc_dir

    @staticmethod
    def load_stage(doc_dir: Path, stage_name: str) -> dict[str, Any] | list[Any] | None:
        """Loads a stage payload if previously saved."""
        file_path = doc_dir / f"{stage_name}.json"
        if file_path.exists():
            return json.loads(file_path.read_text(encoding="utf-8"))
        return None

    @staticmethod
    def save_stage(doc_dir: Path, stage_name: str, data: Any) -> None:
        """Saves a stage payload to disk as formatted JSON."""
        file_path = doc_dir / f"{stage_name}.json"
        payload = data.model_dump() if isinstance(data, BaseModel) else data
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

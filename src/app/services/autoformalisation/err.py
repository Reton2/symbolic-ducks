from __future__ import annotations


class AutoformalizationError(Exception):
    """Base exception for all autoformalisation domain failures."""


AutoformalisationError = AutoformalizationError


class LLMExtractionError(AutoformalizationError):
    """Raised when LLM extraction, communication, or JSON schema parsing fails."""


class Z3SandboxExecutionError(AutoformalizationError):
    """Raised when Z3 execution sandbox encounters an unsafe construct or execution error."""


class Z3VerificationError(AutoformalizationError):
    """Raised when a synthesized rule or DAG fails SMT consistency or reachability."""


CEGISVerificationError = Z3VerificationError


class TopologyCycleError(AutoformalizationError):
    """Raised when dependency links contain an unresolvable cycle."""


class CacheCorruptedError(AutoformalizationError):
    """Raised when a cached graph file is malformed or unreadable."""

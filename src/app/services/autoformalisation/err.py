class AutoformalizationError(Exception):
    """Base exception for autoformalisation failures."""


class LLMExtractionError(AutoformalizationError):
    """Raised when LLM extraction or parsing fails."""


class Z3SandboxExecutionError(AutoformalizationError):
    """Raised when Z3 Python sandbox execution or model destruction fails."""


class CEGISVerificationError(AutoformalizationError):
    """Raised when Z3 CEGIS verification fails."""

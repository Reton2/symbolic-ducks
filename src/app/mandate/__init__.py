from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("app.mandate")


def load_mandate_text() -> str:
    """Loads the core algorithmic trading mandate policy markdown text.

    Resolves path relative to repository root with explicit UTF-8 encoding.
    """
    candidates = [
        Path(__file__).resolve().parents[3] / "policy" / "algorithmic_trading.md",
        Path("policy/algorithmic_trading.md"),
    ]
    for path in candidates:
        if path.is_file():
            logger.debug("Loading mandate policy text from %s", path)
            return path.read_text(encoding="utf-8")

    err_msg = (
        "Mandate policy file 'policy/algorithmic_trading.md' not found. "
        f"Searched candidates: {[str(p) for p in candidates]}"
    )
    logger.error(err_msg)
    raise FileNotFoundError(err_msg)


AMM_QRM_2026_V5_TEXT = load_mandate_text()

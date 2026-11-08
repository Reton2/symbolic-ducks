from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_mandate_text() -> str:
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

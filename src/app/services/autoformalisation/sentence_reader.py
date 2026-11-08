from __future__ import annotations

import logging
import re

from app.services.autoformalisation.models import RawSentence

logger = logging.getLogger(__name__)


class SentenceAtomizer:
    @staticmethod
    def clean_text(raw_text: str) -> str:
        cleaned = re.sub(r"[#*`>_\-]+", " ", raw_text)
        cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    @classmethod
    def atomize(cls, raw_text: str) -> list[RawSentence]:
        cleaned = cls.clean_text(raw_text)
        raw_sents = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", cleaned)
            if len(s.strip()) > 15
        ]

        sentences = [RawSentence(index=idx, text=s) for idx, s in enumerate(raw_sents)]
        logger.info(
            "[Stage 1 - Format-Blind Atomizer] Segmented text into %d raw sentences",
            len(sentences),
        )
        return sentences

    @staticmethod
    def window_text_without_regex(
        raw_text: str, target_window_chars: int = 6000
    ) -> list[str]:
        lines = raw_text.splitlines()
        windows: list[str] = []
        current_lines: list[str] = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1
            if current_len + line_len > target_window_chars and current_lines:
                windows.append("\n".join(current_lines))
                overlap = (
                    current_lines[-5:] if len(current_lines) >= 5 else current_lines
                )
                current_lines = list(overlap)
                current_len = sum(len(item) + 1 for item in current_lines)
            current_lines.append(line)
            current_len += line_len

        if current_lines:
            windows.append("\n".join(current_lines))
        return windows

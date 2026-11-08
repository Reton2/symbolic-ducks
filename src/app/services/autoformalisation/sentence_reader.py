import logging
import re

from app.services.autoformalisation.models import RawSentence

logger = logging.getLogger(__name__)


class SentenceAtomizer:
    """Format-blind sentence atomizer preserving semantic sentences across formats."""

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

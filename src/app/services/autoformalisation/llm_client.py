from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from typing import Any

from openai import AsyncOpenAI

from app.config.autoformalizer import AutoformalizerConfig
from app.schemas import (
    AutonomousPolicyGraph,
    ConceptModality,
    InferredEquation,
    InferredVariable,
    VariableRole,
)
from app.services.autoformalisation.models import (
    CausalLink,
    EquationSynthesisResponse,
    RawSentence,
    ResolvedConcept,
    SentenceMapResponse,
)
from app.services.autoformalisation.prompts import (
    EQUATION_SYNTHESIS_PROMPT,
    SENTENCE_MAP_PROMPT,
)
from app.services.autoformalisation.z3_sandbox import Z3SynthesisSandbox

from .err import LLMExtractionError

logger = logging.getLogger(__name__)


class LLMMapReduceExtractor:
    """Concurrent map-reduce entity extractor with bounded async concurrency (max 16)."""

    _ORDINAL_KEYWORDS: frozenset[str] = frozenset(
        {
            "ordinal",
            "tier",
            "stage",
            "level",
            "rank",
        }
    )
    _CATEGORICAL_NAME_KEYWORDS: frozenset[str] = frozenset(
        {
            "categorical",
            "status",
            "mode",
            "state",
            "verdict",
            "directive",
            "regime",
            "posture",
            "decision",
            "trigger",
            "compliance",
            "phase",
            "authority",
        }
    )
    _CATEGORICAL_LABEL_KEYWORDS: frozenset[str] = frozenset(
        {
            "state_",
            "continue",
            "halt",
            "valid",
            "rejected",
            "connected",
            "dropped",
            "allow",
            "intercept",
            "prohibited",
        }
    )

    def __init__(self, client: AsyncOpenAI, config: AutoformalizerConfig) -> None:
        self.client = client
        self.config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrency)

    @classmethod
    def from_defaults(cls, config: AutoformalizerConfig) -> LLMMapReduceExtractor:
        """Factory constructor using default AsyncOpenAI client configuration."""
        client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)
        return cls(client=client, config=config)

    @staticmethod
    def extract_json_payload(raw_content: str) -> str:
        """Extract clean JSON string from raw LLM output, stripping markdown fences if present."""
        text = raw_content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    @staticmethod
    def extract_python_code(raw_content: str) -> str:
        """Extract clean executable Python code from raw LLM output, stripping markdown fences."""
        text = raw_content.strip()
        fenced = re.search(
            r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE
        )
        if fenced:
            return fenced.group(1).strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:python|py|json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    @classmethod
    def infer_concept_modality(
        cls,
        sort: str,
        ordinal_levels: dict[int, str] | None,
        name: str = "",
    ) -> ConceptModality:
        """Classify a concept into numerical, ordinal, or categorical modality."""
        if not ordinal_levels:
            return ConceptModality.NUMERICAL

        low_name = name.lower()
        if any(w in low_name for w in cls._ORDINAL_KEYWORDS):
            return ConceptModality.ORDINAL

        if any(w in low_name for w in cls._CATEGORICAL_NAME_KEYWORDS):
            return ConceptModality.CATEGORICAL

        labels_joined = " ".join(ordinal_levels.values()).lower()
        if any(w in labels_joined for w in cls._CATEGORICAL_LABEL_KEYWORDS):
            return ConceptModality.CATEGORICAL

        return ConceptModality.ORDINAL

    async def _extract_chunk(
        self,
        batch: list[RawSentence],
        batch_idx: int,
        total_batches: int,
    ) -> SentenceMapResponse:
        batch_text = "\n".join(f"[{s.index}] {s.text}" for s in batch)
        async with self._semaphore:
            logger.info(
                "Acquired concurrency slot for batch %d/%d (%d sentences)",
                batch_idx + 1,
                total_batches,
                len(batch),
            )
            try:
                res = await self.client.chat.completions.create(
                    model=self.config.model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SENTENCE_MAP_PROMPT},
                        {"role": "user", "content": batch_text},
                    ],
                    extra_body={
                        "reasoning": {"enabled": True},
                        "provider": {"only": ["alibaba"], "allow_fallbacks": False},
                    },
                    temperature=self.config.temperature,
                )
            except Exception as err:
                logger.error(
                    "LLM batch %d/%d request failed: %s",
                    batch_idx + 1,
                    total_batches,
                    err,
                )
                raise LLMExtractionError(
                    f"LLM batch {batch_idx + 1} call failed: {err}"
                ) from err

        raw_content = res.choices[0].message.content or "{}"
        logger.info(
            "Batch %d/%d RAW LLM output: %s", batch_idx + 1, total_batches, raw_content
        )
        clean_content = self.extract_json_payload(raw_content)
        try:
            response = SentenceMapResponse.model_validate_json(clean_content)
            logger.info(
                "Batch %d/%d successfully mapped: %d entities, %d causal links",
                batch_idx + 1,
                total_batches,
                len(response.entities),
                len(response.causal_links),
            )
            return response
        except Exception as err:
            logger.error(
                "LLM batch %d/%d JSON validation failed: %s",
                batch_idx + 1,
                total_batches,
                err,
            )
            raise LLMExtractionError(
                f"Invalid JSON from batch {batch_idx + 1}: {err}"
            ) from err

    async def map_sentences(
        self, sentences: list[RawSentence]
    ) -> list[SentenceMapResponse]:
        batches = [
            sentences[i : i + self.config.chunk_size]
            for i in range(0, len(sentences), self.config.chunk_size)
        ]
        if not batches:
            return []

        logger.info(
            "[Stage 2A - Map Phase] Dispatching %d batches to %s (max concurrency: %d)",
            len(batches),
            self.config.model,
            self.config.max_concurrency,
        )
        tasks = [
            asyncio.create_task(self._extract_chunk(batch, idx, len(batches)))
            for idx, batch in enumerate(batches)
        ]
        results = await asyncio.gather(*tasks)
        logger.info(
            "Successfully completed %d concurrent LLM map batches", len(results)
        )
        return list(results)

    @staticmethod
    def _merge_entity(
        merged_entities: dict[str, ResolvedConcept],
        ent: Any,
    ) -> None:
        """Merge a parsed entity into the collection of canonical resolved concepts."""
        if ent.id not in merged_entities:
            merged_entities[ent.id] = ResolvedConcept(
                cid=ent.id,
                human_name=ent.name or ent.id,
                sort=ent.sort,
                ordinal_levels=ent.ordinal_levels,
                min_bound=ent.min_bound,
                max_bound=ent.max_bound,
                default_value=ent.min_bound,
            )
            return

        existing = merged_entities[ent.id]
        if ent.ordinal_levels and not existing.ordinal_levels:
            existing.ordinal_levels = ent.ordinal_levels
            existing.sort = ent.sort
            existing.max_bound = ent.max_bound
        if ent.name and len(ent.name) > len(existing.human_name):
            existing.human_name = ent.name

    @staticmethod
    def _merge_link(
        merged_entities: dict[str, ResolvedConcept],
        all_links: list[CausalLink],
        link: CausalLink,
    ) -> None:
        """Merge causal links and ensure endpoint entities are tracked."""
        all_links.append(link)
        for eid in [link.target_id, *link.parent_ids]:
            if not eid:
                continue
            if eid not in merged_entities:
                merged_entities[eid] = ResolvedConcept(
                    cid=eid,
                    human_name=eid.replace("_", " ").title(),
                    sort="real",
                )
            merged_entities[eid].sentence_ids.add(link.sentence_id)

    def reduce_results(
        self,
        responses: list[SentenceMapResponse],
        sentences: list[RawSentence],
    ) -> tuple[dict[str, ResolvedConcept], list[CausalLink]]:
        merged_entities: dict[str, ResolvedConcept] = {}
        all_links: list[CausalLink] = []
        sent_dict = {s.index: s.text for s in sentences}

        for resp in responses:
            for ent in resp.entities:
                self._merge_entity(merged_entities, ent)
            for link in resp.causal_links:
                self._merge_link(merged_entities, all_links, link)

        for concept in merged_entities.values():
            sids = sorted(concept.sentence_ids)
            concept.source_excerpts = [sent_dict.get(idx, "") for idx in sids[:3]]

        logger.info(
            "[Stage 2B - Entity Resolution] Unified %d canonical concepts and %d causal links",
            len(merged_entities),
            len(all_links),
        )
        return merged_entities, all_links

    @classmethod
    def _build_synthesis_payload(
        cls,
        concepts: dict[str, ResolvedConcept],
        links: list[CausalLink],
    ) -> dict[str, Any]:
        entity_specs: dict[str, dict[str, Any]] = {}
        for c in concepts.values():
            entity_specs[c.cid] = {
                "id": c.cid,
                "name": c.human_name,
                "modality": cls.infer_concept_modality(
                    c.sort, c.ordinal_levels, c.human_name
                ),
                "sort": str(c.sort),
                "min_bound": c.min_bound,
                "max_bound": c.max_bound,
                "ordinal_levels": c.ordinal_levels,
            }

        grouped_links: dict[str, list[CausalLink]] = {}
        for link in links:
            grouped_links.setdefault(link.target_id, []).append(link)

        targets: dict[str, dict[str, Any]] = {}
        for tid, tlinks in grouped_links.items():
            parents: list[str] = []
            thresholds: list[str] = []
            for lnk in tlinks:
                for pid in lnk.parent_ids:
                    if pid != tid and pid not in parents:
                        parents.append(pid)
                for th in lnk.qualitative_thresholds:
                    if th not in thresholds:
                        thresholds.append(th)

            targets[tid] = {
                "target_id": tid,
                "parent_ids": parents,
                "logic_summaries": [
                    lnk.logic_summary for lnk in tlinks if lnk.logic_summary
                ],
                "qualitative_thresholds": thresholds,
            }

        return {
            "entities": entity_specs,
            "targets": targets,
        }

    async def synthesize_equations(
        self,
        concepts: dict[str, ResolvedConcept],
        links: list[CausalLink],
    ) -> EquationSynthesisResponse:
        payload = self._build_synthesis_payload(concepts, links)
        logger.info(
            "[Stage 2C - SMT Equation Synthesis] Generating pure Z3 Python model via %s...",
            self.config.model,
        )
        async with self._semaphore:
            try:
                res = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": EQUATION_SYNTHESIS_PROMPT},
                        {"role": "user", "content": json.dumps(payload)},
                    ],
                    extra_body={
                        "reasoning": {"enabled": True},
                        "provider": {"only": ["alibaba"], "allow_fallbacks": False},
                    },
                    temperature=self.config.temperature,
                )
            except Exception as err:
                logger.error("Equation synthesis LLM request failed: %s", err)
                raise LLMExtractionError(f"Equation synthesis failed: {err}") from err

        raw_content = res.choices[0].message.content or ""
        sandbox = Z3SynthesisSandbox(concepts=concepts, links=links)
        try:
            eq_response = sandbox.execute(raw_content)
            logger.info(
                "[Stage 2D - Z3 Sandbox Execution] Constructed & destructed %d parameters and %d symbolic equations",
                len(eq_response.parameters),
                len(eq_response.equations),
            )
            return eq_response
        except Exception as err:
            logger.error("Equation synthesis Z3 sandbox execution failed: %s", err)
            raise LLMExtractionError(
                f"Equation synthesis sandbox execution failed: {err}"
            ) from err

    def build_graph(
        self,
        concepts: dict[str, ResolvedConcept],
        eq_data: EquationSynthesisResponse,
        sentences: list[RawSentence],
        log: list[str],
    ) -> AutonomousPolicyGraph:
        variables: dict[str, InferredVariable] = {}
        for eid, ent in concepts.items():
            variables[eid] = InferredVariable(
                var_id=eid,
                human_name=ent.human_name,
                role=VariableRole.INPUT,
                sort=ent.sort,
                ordinal_levels=ent.ordinal_levels,
                min_bound=ent.min_bound,
                max_bound=ent.max_bound,
                default_value=ent.default_value,
                source_sentence_ids=sorted(ent.sentence_ids),
                source_excerpts=ent.source_excerpts,
            )

        for pid, p in eq_data.parameters.items():
            variables[pid] = InferredVariable(
                var_id=pid,
                human_name=p.human_name or pid,
                role=VariableRole.PARAMETER,
                sort=p.sort,
                min_bound=p.min_bound,
                max_bound=p.max_bound,
                default_value=p.default_value,
                source_sentence_ids=p.source_sentence_ids,
            )

        equations: dict[str, InferredEquation] = {}
        for tid, eq in eq_data.equations.items():
            if tid in variables:
                equations[tid] = InferredEquation(
                    equation_id=eq.equation_id or f"eq_{tid}",
                    target_var=tid,
                    dependencies=[d for d in eq.dependencies if d in variables],
                    smt_expression=eq.smt_expression,
                    natural_language_logic=eq.natural_language_logic,
                    source_sentence_ids=eq.source_sentence_ids,
                )

        return AutonomousPolicyGraph(
            graph_id=f"smt_hypergraph_{str(uuid.uuid4())[:6]}",
            title="Autonomously Inferred Sentence-Stream Policy Graph",
            raw_document_text="\n\n".join(s.text for s in sentences),
            sentence_count=len(sentences),
            variables=variables,
            equations=equations,
            cegis_compiler_log=log,
        )


# Backward-compatible function aliases for callers referencing module-level routines
extract_json_payload = LLMMapReduceExtractor.extract_json_payload
extract_python_code = LLMMapReduceExtractor.extract_python_code
infer_concept_modality = LLMMapReduceExtractor.infer_concept_modality

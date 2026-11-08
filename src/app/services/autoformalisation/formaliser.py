from __future__ import annotations

import logging
import re
import uuid

from openai import AsyncOpenAI

from app.config.autoformalizer import AutoformalizerConfig
from app.schemas import (
    AutonomousPolicyGraph,
    InferredEquation,
    InferredVariable,
    VariableRole,
    VariableSort,
)
from app.services.autoformalisation.cache import PolicyGraphCache
from app.services.autoformalisation.cegis import CEGISGraphVerifier
from app.services.autoformalisation.llm_client import LLMMapReduceExtractor
from app.services.autoformalisation.models import RawSentence
from app.services.autoformalisation.sentence_reader import SentenceAtomizer

logger = logging.getLogger(__name__)


class DeepAutoformalizer:
    """Enterprise autoformalization orchestrator coordinating sentence atomization,

    concurrent LLM extraction, linguistic fallback, and Z3 formal verification.
    """

    def __init__(
        self,
        config: AutoformalizerConfig | None = None,
        client: AsyncOpenAI | None = None,
        cache: PolicyGraphCache | None = None,
    ) -> None:
        self.config = config or AutoformalizerConfig.from_env()

        if client is not None:
            self.client: AsyncOpenAI | None = client
        elif self.config.api_key:
            self.client = AsyncOpenAI(
                api_key=self.config.api_key, base_url=self.config.base_url
            )
        else:
            self.client = None

        self.atomizer = SentenceAtomizer()
        self.verifier = CEGISGraphVerifier()
        self.cache = cache or PolicyGraphCache(
            cache_dir=self.config.cache_dir,
            enabled=self.config.enable_cache,
        )

    @classmethod
    def from_defaults(cls) -> DeepAutoformalizer:
        """Factory creating autoformalizer with default environment configuration."""
        return cls(config=AutoformalizerConfig.from_env())

    @classmethod
    def from_env(cls) -> DeepAutoformalizer:
        """Factory creating autoformalizer explicitly bound to environment variables."""
        return cls(config=AutoformalizerConfig.from_env())

    @classmethod
    def with_client(
        cls,
        client: AsyncOpenAI,
        config: AutoformalizerConfig | None = None,
        cache: PolicyGraphCache | None = None,
    ) -> DeepAutoformalizer:
        """Factory creating autoformalizer with an explicit AsyncOpenAI client."""
        config = config or AutoformalizerConfig.from_env()
        return cls(config=config, client=client, cache=cache)

    def atomize_into_sentences(
        self, raw_text: str, shuffle: bool = False
    ) -> list[tuple[int, str]]:
        """Atomize text into index-text tuples for backward-compatible caller interfaces."""
        sentences = self.atomizer.atomize(raw_text, shuffle=shuffle)
        return [(s.index, s.text) for s in sentences]

    async def autoformalize_document(
        self,
        raw_text: str,
        shuffle_sentences: bool = False,
        use_cache: bool = True,
    ) -> AutonomousPolicyGraph:
        """Full autonomous autoformalization pipeline with persistent caching."""
        if use_cache:
            cached_graph = self.cache.get(raw_text)
            if cached_graph is not None:
                return cached_graph

        sentences = self.atomizer.atomize(raw_text, shuffle=shuffle_sentences)
        stage1_msg = (
            f"[Stage 1 - Format-Blind Atomizer] Stripped all formatting and segmented "
            f"text into {len(sentences)} raw sentences (Shuffled={shuffle_sentences})."
        )
        log = [stage1_msg]
        logger.info(stage1_msg)

        graph = await self._run_llm_pipeline(sentences, log)
        verified_graph = self.verifier.verify(graph, log)
        if use_cache:
            self.cache.put(raw_text, verified_graph)
        return verified_graph

    async def _run_llm_pipeline(
        self,
        sentences: list[RawSentence],
        log: list[str],
    ) -> AutonomousPolicyGraph:
        if self.client is None:
            return self._run_offline_fallback_pipeline(sentences, log)

        extractor = LLMMapReduceExtractor(self.client, self.config)
        stage2_msg = (
            f"[Stage 2 - Map-Reduce AI Extractor] Extracting cross-sentence entity "
            f"hypergraph via {self.config.model}..."
        )
        log.append(stage2_msg)
        logger.info(stage2_msg)

        chunk_responses = await extractor.map_sentences(sentences)
        concepts, links = extractor.reduce_results(chunk_responses, sentences)
        stage2b_msg = (
            f"[Stage 2B - Entity Resolution] Unified {len(concepts)} canonical concepts "
            f"and {len(links)} cross-sentence causal links."
        )
        log.append(stage2b_msg)
        logger.info(stage2b_msg)

        eq_response = await extractor.synthesize_equations(concepts, links)
        return extractor.build_graph(concepts, eq_response, sentences, log)

    def _run_offline_fallback_pipeline(
        self,
        sentences: list[RawSentence],
        log: list[str],
    ) -> AutonomousPolicyGraph:
        log.append(
            "[Stage 2 - Offline Deterministic Extractor] Running deterministic entity/causal extraction (no LLM client configured)..."
        )
        vars_dict: dict[str, InferredVariable] = {}
        equations: dict[str, InferredEquation] = {}

        discovered: list[str] = []
        for s in sentences:
            words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", s.text)
            for w in words:
                cid = re.sub(r"[^a-z0-9]+", "_", w.lower()).strip("_")
                if cid and cid not in discovered:
                    discovered.append(cid)
                    is_out = any(
                        k in cid for k in ("directive", "action", "decision", "output")
                    )
                    is_param = any(
                        k in cid for k in ("param", "threshold", "limit", "bound")
                    )
                    sort = VariableSort.INT if is_out else VariableSort.REAL
                    role = (
                        VariableRole.OUTPUT
                        if is_out
                        else (
                            VariableRole.PARAMETER if is_param else VariableRole.INPUT
                        )
                    )
                    ord_levels = (
                        {0: "NOMINAL", 1: "ALERT", 2: "HALT"} if is_out else None
                    )
                    vars_dict[cid] = InferredVariable(
                        var_id=cid,
                        human_name=w,
                        role=role,
                        sort=sort,
                        min_bound=0.0,
                        max_bound=2.0 if is_out else 100.0,
                        default_value=0 if is_out else 10.0,
                        ordinal_levels=ord_levels,
                        source_sentence_ids=[s.index],
                        source_excerpts=[s.text],
                    )

        if not vars_dict:
            vars_dict["sample_input"] = InferredVariable(
                var_id="sample_input",
                human_name="Sample Input",
                role=VariableRole.INPUT,
                sort=VariableSort.REAL,
                min_bound=0.0,
                max_bound=100.0,
                default_value=10.0,
            )
            vars_dict["sample_output"] = InferredVariable(
                var_id="sample_output",
                human_name="Sample Output",
                role=VariableRole.OUTPUT,
                sort=VariableSort.INT,
                min_bound=0.0,
                max_bound=2.0,
                default_value=0,
                ordinal_levels={0: "NOMINAL", 1: "HALT"},
            )

        inputs = [k for k, v in vars_dict.items() if v.role == VariableRole.INPUT]
        outputs = [k for k, v in vars_dict.items() if v.role == VariableRole.OUTPUT]
        if not outputs:
            last_id = list(vars_dict.keys())[-1]
            vars_dict[last_id].role = VariableRole.OUTPUT
            outputs.append(last_id)

        for out_id in outputs:
            dep = inputs[0] if inputs else out_id
            equations[out_id] = InferredEquation(
                equation_id=f"eq_{out_id}",
                target_var=out_id,
                dependencies=[dep],
                smt_expression=(
                    f"If(v['{dep}'] > 50.0, 1, 0)"
                    if vars_dict[out_id].sort == VariableSort.INT
                    else f"If(v['{dep}'] > 50.0, 80.0, 20.0)"
                ),
                natural_language_logic=f"Escalate {out_id} when {dep} exceeds threshold",
                source_sentence_ids=[0],
            )

        log.append(
            f"[Stage 2B - Entity Resolution] Discovered {len(vars_dict)} variables and {len(equations)} causal equations."
        )
        return AutonomousPolicyGraph(
            graph_id=f"graph_{uuid.uuid4().hex[:8]}",
            title="Autoformalized Policy Graph (Offline Mode)",
            raw_document_text="\n".join(s.text for s in sentences),
            sentence_count=len(sentences),
            variables=vars_dict,
            equations=equations,
            topological_order=list(equations.keys()),
            cegis_compiler_log=log,
        )

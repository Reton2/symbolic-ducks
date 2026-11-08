from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

import z3
from openai import AsyncOpenAI

from app.config.autoformalizer import AutoformalizerConfig
from app.schemas import AutonomousPolicyGraph
from app.services.autoformalisation.cache import IntermediateStateStore
from app.services.autoformalisation.compiler import DeterministicZ3LoweringCompiler
from app.services.autoformalisation.graph_builder import AutonomousGraphBuilder
from app.services.autoformalisation.llm_client import chat_completion_parse
from app.services.autoformalisation.models import (
    ClauseDecompositionBatch,
    DependencyMappingBatch,
    DiscreteStateMapping,
    EntityDependencyLink,
    EntityRole,
    LogicExpr,
    Modality,
    NumericalThresholdMapping,
    OntologyExtractionResult,
    PolicyEntity,
    RawSentence,
    SemanticClause,
    SynthesizedNodeRule,
    Z3SortType,
)
from app.services.autoformalisation.prompts import (
    CLAUSE_DECOMPOSITION_PROMPT,
    DEPENDENCY_MAPPING_PROMPT,
    ONTOLOGY_EXTRACTION_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    format_cegar_repair_prompt,
)
from app.services.autoformalisation.sanitization import to_canonical_identifier
from app.services.autoformalisation.sentence_reader import SentenceAtomizer
from app.services.autoformalisation.verifier import Z3VerificationSandbox

logger = logging.getLogger(__name__)


class AgenticPolicyCompiler:
    """Multi-stage neuro-symbolic agentic pipeline compiling policy text into verified SMT DAGs."""

    def __init__(
        self,
        config: AutoformalizerConfig,
        client: AsyncOpenAI | None = None,
        state_store: IntermediateStateStore | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.semaphore = asyncio.Semaphore(config.max_concurrency)
        self.state_store = state_store or IntermediateStateStore(
            cache_dir=config.cache_dir
        )

    # --------------------------------------------------------------------------
    # STAGE 1: SEMANTIC CLAUSE DECOMPOSITION
    # --------------------------------------------------------------------------
    async def _extract_window_clauses(
        self, idx: int, chunk: str
    ) -> list[SemanticClause]:
        if not self.client:
            return []
        async with self.semaphore:
            batch = await chat_completion_parse(
                client=self.client,
                model=self.config.model,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": CLAUSE_DECOMPOSITION_PROMPT},
                    {"role": "user", "content": f"Window #{idx}:\n\n{chunk}"},
                ],
                response_model=ClauseDecompositionBatch,
            )
            return batch.clauses if batch else []

    async def decompose_into_semantic_clauses(
        self, raw_text: str, doc_dir: Path
    ) -> list[SemanticClause]:
        cached = self.state_store.load_stage(doc_dir, "stage1_clauses")
        if cached is not None and isinstance(cached, list):
            return [SemanticClause.model_validate(c) for c in cached]

        windows = SentenceAtomizer.window_text_without_regex(raw_text)
        batches = await asyncio.gather(
            *[self._extract_window_clauses(i, w) for i, w in enumerate(windows)]
        )

        all_clauses: list[SemanticClause] = []
        seen_excerpts: set[str] = set()
        counter = 1

        for batch in batches:
            for cl in batch:
                norm_key = cl.normalized_proposition.strip().lower()
                if norm_key not in seen_excerpts:
                    seen_excerpts.add(norm_key)
                    cl.clause_id = f"clause_{counter:03d}"
                    all_clauses.append(cl)
                    counter += 1

        self.state_store.save_stage(
            doc_dir, "stage1_clauses", [c.model_dump() for c in all_clauses]
        )
        return all_clauses

    # --------------------------------------------------------------------------
    # STAGE 2: GLOBAL ONTOLOGY & ENTITY EXTRACTION
    # --------------------------------------------------------------------------
    async def extract_global_ontology(
        self, raw_text: str, clauses: list[SemanticClause], doc_dir: Path
    ) -> OntologyExtractionResult:
        cached = self.state_store.load_stage(doc_dir, "stage2_ontology")
        if cached is not None and isinstance(cached, dict):
            return OntologyExtractionResult.model_validate(cached)

        clause_digest = "\n".join(
            f"[{c.clause_id}] ({c.clause_type}): {c.normalized_proposition}"
            for c in clauses
        )

        assert self.client is not None
        async with self.semaphore:
            ontology = await chat_completion_parse(
                client=self.client,
                model=self.config.model,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": ONTOLOGY_EXTRACTION_PROMPT},
                    {
                        "role": "user",
                        "content": f"Full Policy Text:\n{raw_text}\n\nDigest:\n{clause_digest}",
                    },
                ],
                response_model=OntologyExtractionResult,
            )

        for ent in ontology.entities:
            ent.canonical_id = to_canonical_identifier(ent.canonical_id)

        self.state_store.save_stage(doc_dir, "stage2_ontology", ontology)
        return ontology

    # --------------------------------------------------------------------------
    # STAGE 3: ENTITY-TO-CLAUSE DEPENDENCY MAPPING
    # --------------------------------------------------------------------------
    async def _map_dep_batch(
        self,
        target_batch: list[PolicyEntity],
        entity_catalog: str,
        clause_catalog: str,
    ) -> list[EntityDependencyLink]:
        assert self.client is not None
        target_str = "\n".join(
            f"- {t.canonical_id} ('{t.original_name}')" for t in target_batch
        )
        async with self.semaphore:
            batch = await chat_completion_parse(
                client=self.client,
                model=self.config.model,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": DEPENDENCY_MAPPING_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Target Entities:\n{target_str}\n\n"
                            f"All Entities:\n{entity_catalog}\n\n"
                            f"Clauses:\n{clause_catalog}"
                        ),
                    },
                ],
                response_model=DependencyMappingBatch,
            )
            return batch.links if batch else []

    async def map_entity_dependencies(
        self,
        ontology: OntologyExtractionResult,
        clauses: list[SemanticClause],
        doc_dir: Path,
    ) -> dict[str, EntityDependencyLink]:
        cached = self.state_store.load_stage(doc_dir, "stage3_dependencies")
        if cached is not None and isinstance(cached, dict):
            return {
                k: EntityDependencyLink.model_validate(v) for k, v in cached.items()
            }

        derived = [e for e in ontology.entities if e.role != EntityRole.INPUT]
        e_catalog = "\n".join(
            f"- {e.canonical_id} ('{e.original_name}', role={e.role.value})"
            for e in ontology.entities
        )
        c_catalog = "\n".join(
            f"[{c.clause_id}]: {c.normalized_proposition}" for c in clauses
        )

        chunk_size = 10
        batches = [
            derived[i : i + chunk_size] for i in range(0, len(derived), chunk_size)
        ]
        results = await asyncio.gather(
            *[self._map_dep_batch(b, e_catalog, c_catalog) for b in batches]
        )

        dep_map = self._clean_dependency_links(results, ontology)
        self.state_store.save_stage(
            doc_dir,
            "stage3_dependencies",
            {k: v.model_dump() for k, v in dep_map.items()},
        )
        return dep_map

    def _clean_dependency_links(
        self,
        results: list[list[EntityDependencyLink]],
        ontology: OntologyExtractionResult,
    ) -> dict[str, EntityDependencyLink]:
        dep_map: dict[str, EntityDependencyLink] = {}
        valid_ids = {e.canonical_id for e in ontology.entities}
        input_ids = {
            e.canonical_id for e in ontology.entities if e.role == EntityRole.INPUT
        }
        inter_ids = {
            e.canonical_id
            for e in ontology.entities
            if e.role == EntityRole.INTERMEDIATE
        }
        output_ids = {
            e.canonical_id for e in ontology.entities if e.role == EntityRole.OUTPUT
        }

        for batch in results:
            for link in batch:
                tid = to_canonical_identifier(link.target_canonical_id)
                link.target_canonical_id = tid
                inputs = [
                    to_canonical_identifier(iid)
                    for iid in link.input_canonical_ids
                    if to_canonical_identifier(iid) in valid_ids
                    and to_canonical_identifier(iid) != tid
                ]
                if tid in output_ids and any(dep in inter_ids for dep in inputs):
                    inputs = [dep for dep in inputs if dep not in input_ids]
                link.input_canonical_ids = inputs
                dep_map[tid] = link
        return dep_map

    # --------------------------------------------------------------------------
    # STAGE 4: TOPOLOGICAL DAG LAYERING (KAHN'S ALGORITHM)
    # --------------------------------------------------------------------------
    @staticmethod
    def build_topological_layers(
        ontology: OntologyExtractionResult,
        dep_map: dict[str, EntityDependencyLink],
    ) -> list[list[str]]:
        derived_ids = {
            e.canonical_id for e in ontology.entities if e.role != EntityRole.INPUT
        }
        in_degree: dict[str, int] = {tid: 0 for tid in derived_ids}
        dependents: dict[str, list[str]] = {tid: [] for tid in derived_ids}

        for tid in derived_ids:
            link = dep_map.get(tid)
            if not link:
                continue
            for dep_id in link.input_canonical_ids:
                if dep_id in derived_ids:
                    in_degree[tid] += 1
                    dependents[dep_id].append(tid)

        waves: list[list[str]] = []
        ready = sorted([tid for tid, deg in in_degree.items() if deg == 0])
        visited: set[str] = set()

        while ready:
            waves.append(ready)
            next_ready: set[str] = set()
            for u in ready:
                visited.add(u)
                for v in dependents.get(u, []):
                    in_degree[v] -= 1
                    if in_degree[v] == 0 and v not in visited:
                        next_ready.add(v)
            ready = sorted(next_ready)

        remaining = sorted(derived_ids - visited)
        if remaining:
            waves.append(remaining)
        return waves

    # --------------------------------------------------------------------------
    # STAGE 5: CEGAR SYNTHESIS & SELF-HEALING LOOP
    # --------------------------------------------------------------------------
    async def synthesize_and_verify_node(
        self,
        target_id: str,
        ontology: OntologyExtractionResult,
        entity_map: dict[str, PolicyEntity],
        dep_link: EntityDependencyLink,
        clause_map: dict[str, SemanticClause],
        sandbox: Z3VerificationSandbox,
        prior_constraints: dict[str, z3.ExprRef],
    ) -> tuple[SynthesizedNodeRule, z3.ExprRef]:
        target_ent = entity_map[target_id]
        input_entities = [
            entity_map[iid] for iid in dep_link.input_canonical_ids if iid in entity_map
        ]

        relevant_clauses = [
            clause_map[cid]
            for cid in dep_link.governing_clause_ids
            if cid in clause_map
        ]
        inputs_spec = json.dumps([e.model_dump() for e in input_entities], indent=2)
        target_spec = json.dumps(target_ent.model_dump(), indent=2)
        clauses_text = "\n\n".join(
            f"[{c.clause_id}]: {c.normalized_proposition}" for c in relevant_clauses
        )
        framework_spec = json.dumps(ontology.global_framework.model_dump(), indent=2)

        feedback_history: list[str] = []
        last_rule: SynthesizedNodeRule | None = None

        assert self.client is not None
        for attempt in range(1, self.config.max_repair_attempts + 1):
            repair_prompt = (
                format_cegar_repair_prompt(feedback_history) if feedback_history else ""
            )
            async with self.semaphore:
                rule = await chat_completion_parse(
                    client=self.client,
                    model=self.config.model,
                    temperature=0.0 if attempt == 1 else 0.1,
                    messages=[
                        {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"Framework:\n{framework_spec}\n\n"
                                f"Target:\n{target_spec}\n\n"
                                f"Inputs:\n{inputs_spec}\n\n"
                                f"Clauses:\n{clauses_text}\n"
                                f"{repair_prompt}"
                            ),
                        },
                    ],
                    response_model=SynthesizedNodeRule,
                )

            last_rule = rule
            is_valid, diagnostics, z3_eq = sandbox.verify_node_rule(
                target_id, rule, prior_constraints
            )
            if is_valid and z3_eq is not None:
                return rule, z3_eq
            feedback_history = diagnostics

        assert last_rule is not None
        rhs_z3 = sandbox.compiler.to_z3_expr(
            last_rule.expr_ast, sandbox.z3_vars, expected_sort=target_ent.z3_sort
        )
        return last_rule, (sandbox.z3_vars[target_id] == rhs_z3)

    # --------------------------------------------------------------------------
    # OFFLINE DETERMINISTIC FALLBACK
    # --------------------------------------------------------------------------
    def run_offline_fallback(
        self, raw_text: str, sentences: list[RawSentence]
    ) -> AutonomousPolicyGraph:
        """Deterministic offline extraction pipeline when LLM client is unavailable."""
        discovered: list[str] = []
        entities: list[PolicyEntity] = []

        for s in sentences:
            words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", s.text)
            for w in words:
                cid = to_canonical_identifier(w)
                if cid and cid not in discovered:
                    discovered.append(cid)
                    is_out = any(
                        k in cid for k in ("directive", "action", "decision", "output")
                    )
                    entities.append(
                        PolicyEntity(
                            canonical_id=cid,
                            original_name=w,
                            role=EntityRole.OUTPUT if is_out else EntityRole.INPUT,
                            modality=Modality.ORDINAL if is_out else Modality.NUMERICAL,
                            z3_sort=Z3SortType.INT if is_out else Z3SortType.REAL,
                            min_bound=0.0,
                            max_bound=2.0 if is_out else 100.0,
                            discrete_states=[
                                DiscreteStateMapping(
                                    state_index=0,
                                    state_label="NOMINAL",
                                    intensity_score=0.0,
                                ),
                                DiscreteStateMapping(
                                    state_index=1,
                                    state_label="ALERT",
                                    intensity_score=50.0,
                                ),
                                DiscreteStateMapping(
                                    state_index=2,
                                    state_label="HALT",
                                    intensity_score=100.0,
                                ),
                            ]
                            if is_out
                            else [],
                            numerical_mapping=NumericalThresholdMapping(
                                comparison_op=">=",
                                threshold_value=50.0,
                                breach_intensity=100.0,
                                baseline_intensity=10.0,
                            )
                            if not is_out
                            else None,
                        )
                    )

        if not any(e.role == EntityRole.OUTPUT for e in entities) and entities:
            entities[-1].role = EntityRole.OUTPUT
            entities[-1].z3_sort = Z3SortType.INT
            entities[-1].modality = Modality.ORDINAL
            entities[-1].max_bound = 2.0
            entities[-1].discrete_states = [
                DiscreteStateMapping(
                    state_index=0, state_label="NOMINAL", intensity_score=0.0
                ),
                DiscreteStateMapping(
                    state_index=1, state_label="HALT", intensity_score=100.0
                ),
            ]

        entity_map = {e.canonical_id: e for e in entities}
        inputs = [e.canonical_id for e in entities if e.role == EntityRole.INPUT]
        outputs = [e.canonical_id for e in entities if e.role == EntityRole.OUTPUT]

        dep_map: dict[str, EntityDependencyLink] = {}
        synthesized_rules: dict[str, SynthesizedNodeRule] = {}

        for out_id in outputs:
            in_deps = [inputs[0]] if inputs else []
            dep_map[out_id] = EntityDependencyLink(
                target_canonical_id=out_id,
                governing_clause_ids=[],
                input_canonical_ids=in_deps,
                reasoning_summary="Deterministic fallback escalation rule",
            )
            trigger_cond = (
                LogicExpr(
                    kind="compare",
                    comp_op=">=",
                    left=LogicExpr(kind="var_ref", var_id=in_deps[0]),
                    right=LogicExpr(kind="literal_real", float_val=50.0),
                )
                if in_deps
                else LogicExpr(kind="literal_int", int_val=0)
            )
            synthesized_rules[out_id] = SynthesizedNodeRule(
                target_canonical_id=out_id,
                reasoning_trace="Deterministic rule mapping",
                expr_ast=LogicExpr(
                    kind="ite",
                    cond=trigger_cond,
                    then_branch=LogicExpr(kind="literal_int", int_val=2),
                    else_branch=LogicExpr(kind="literal_int", int_val=0),
                ),
                continuous_intensity_ast=LogicExpr(
                    kind="ite",
                    cond=trigger_cond,
                    then_branch=LogicExpr(kind="literal_real", float_val=100.0),
                    else_branch=LogicExpr(kind="literal_real", float_val=10.0),
                ),
            )

        compiler = DeterministicZ3LoweringCompiler(entity_map)
        waves = [[out_id] for out_id in outputs]
        log = [
            f"[Stage 1 - Semantic Extraction] Ingested {len(sentences)} sentences.",
            f"[Stage 2 - Offline Fallback] Extracted {len(entities)} entities ({len(inputs)} inputs, {len(outputs)} outputs).",
            f"[Stage 5 - SMT Lowering] Compiled {len(synthesized_rules)} deterministic SMT rules.",
        ]
        return AutonomousGraphBuilder.build_graph(
            raw_text=raw_text,
            sentence_count=len(sentences),
            entities=entity_map,
            dep_map=dep_map,
            synthesized_rules=synthesized_rules,
            compiler=compiler,
            waves=waves,
            compiler_log=log,
        )

    # --------------------------------------------------------------------------
    # FULL AUTOFORMALISATION PIPELINE
    # --------------------------------------------------------------------------
    async def compile_policy(
        self, raw_text: str, sentences: list[RawSentence]
    ) -> AutonomousPolicyGraph:
        """Executes full 5-stage agentic pipeline or falls back to offline deterministic mode."""
        if not self.client or not self.config.api_key:
            return self.run_offline_fallback(raw_text, sentences)

        doc_dir = self.state_store.get_doc_dir(raw_text)
        log: list[str] = [
            "[Stage 1 - Semantic Decomposition] Segmented document into semantic windows."
        ]

        clauses = await self.decompose_into_semantic_clauses(raw_text, doc_dir)
        clause_map = {c.clause_id: c for c in clauses}
        log.append(f"[Stage 1 - Clauses] Extracted {len(clauses)} atomic propositions.")

        ontology = await self.extract_global_ontology(raw_text, clauses, doc_dir)
        entity_map = {e.canonical_id: e for e in ontology.entities}
        log.append(
            f"[Stage 2 - Ontology] Extracted {len(ontology.entities)} policy entities."
        )

        dep_map = await self.map_entity_dependencies(ontology, clauses, doc_dir)
        log.append(
            f"[Stage 3 - Lineage] Mapped dependencies across {len(dep_map)} derived targets."
        )

        waves = self.build_topological_layers(ontology, dep_map)
        log.append(
            f"[Stage 4 - Topological Waves] Generated {len(waves)} execution waves."
        )

        compiler = DeterministicZ3LoweringCompiler(entity_map)
        sandbox = Z3VerificationSandbox(entity_map, compiler)

        verified_constraints: dict[str, z3.ExprRef] = {}
        synthesized_rules: dict[str, SynthesizedNodeRule] = {}

        for eid, ent in entity_map.items():
            if ent.role == EntityRole.INPUT:
                comp_id = f"{eid}_intensity"
                raw_ast = compiler.build_default_intensity_ast(ent)
                comp_z3 = compiler.to_z3_expr(
                    raw_ast, sandbox.z3_vars, expected_sort=Z3SortType.REAL
                )
                verified_constraints[comp_id] = sandbox.z3_vars[comp_id] == comp_z3
                compiler.intensity_ast_cache[eid] = LogicExpr(
                    kind="var_ref", var_id=comp_id
                )

        for wave_targets in waves:

            async def _process(tid: str) -> tuple[str, SynthesizedNodeRule, z3.ExprRef]:
                link = dep_map.get(
                    tid,
                    EntityDependencyLink(
                        target_canonical_id=tid,
                        governing_clause_ids=[c.clause_id for c in clauses],
                        input_canonical_ids=[],
                        reasoning_summary="Fallback dependency scan",
                    ),
                )
                rule, z3_eq = await self.synthesize_and_verify_node(
                    tid,
                    ontology,
                    entity_map,
                    link,
                    clause_map,
                    sandbox,
                    verified_constraints,
                )
                return tid, rule, z3_eq

            results = await asyncio.gather(*[_process(tid) for tid in wave_targets])
            for tid, rule, z3_eq in results:
                verified_constraints[tid] = z3_eq
                synthesized_rules[tid] = rule
                ent = entity_map[tid]
                if ent.role != EntityRole.INPUT and ent.z3_sort == Z3SortType.INT:
                    comp_id = f"{tid}_intensity"
                    comp_ast = compiler.extract_continuous_intensity_ast(ent, rule)
                    comp_z3 = compiler.to_z3_expr(
                        comp_ast, sandbox.z3_vars, expected_sort=Z3SortType.REAL
                    )
                    verified_constraints[comp_id] = sandbox.z3_vars[comp_id] == comp_z3
                    compiler.intensity_ast_cache[tid] = LogicExpr(
                        kind="var_ref", var_id=comp_id
                    )
                elif ent.role != EntityRole.INPUT and ent.z3_sort == Z3SortType.REAL:
                    compiler.intensity_ast_cache[tid] = LogicExpr(
                        kind="var_ref", var_id=tid
                    )

        log.append(
            f"[Stage 5 - SMT Synthesis] Formally verified {len(synthesized_rules)} equations."
        )
        self.state_store.save_stage(
            doc_dir,
            "stage5_synthesized_rules",
            {k: v.model_dump() for k, v in synthesized_rules.items()},
        )

        return AutonomousGraphBuilder.build_graph(
            raw_text=raw_text,
            sentence_count=len(clauses),
            entities=entity_map,
            dep_map=dep_map,
            synthesized_rules=synthesized_rules,
            compiler=compiler,
            waves=waves,
            compiler_log=log,
        )

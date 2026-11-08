from __future__ import annotations

import uuid

from app.schemas import (
    AutonomousPolicyGraph,
    InferredEquation,
    InferredVariable,
    VariableRole,
    VariableSort,
)
from app.services.autoformalisation.compiler import DeterministicZ3LoweringCompiler
from app.services.autoformalisation.models import (
    EntityDependencyLink,
    EntityRole,
    PolicyEntity,
    SynthesizedNodeRule,
    Z3SortType,
)


def _map_role(role: EntityRole) -> VariableRole:
    if role == EntityRole.INPUT:
        return VariableRole.INPUT
    if role == EntityRole.OUTPUT:
        return VariableRole.OUTPUT
    return VariableRole.INTERMEDIATE


def _map_sort(sort: Z3SortType) -> VariableSort:
    return VariableSort.INT if sort == Z3SortType.INT else VariableSort.REAL


class AutonomousGraphBuilder:
    """Constructs production-grade AutonomousPolicyGraph models from verified SMT rules."""

    @staticmethod
    def _create_variable_from_entity(ent: PolicyEntity) -> InferredVariable:
        ord_levels = (
            {s.state_index: s.state_label for s in ent.discrete_states}
            if ent.discrete_states
            else None
        )
        def_val = (
            0
            if ent.z3_sort == Z3SortType.INT
            else (10.0 if ent.role == EntityRole.INPUT else 0.0)
        )
        return InferredVariable(
            var_id=ent.canonical_id,
            human_name=ent.original_name,
            role=_map_role(ent.role),
            sort=_map_sort(ent.z3_sort),
            min_bound=ent.min_bound,
            max_bound=ent.max_bound,
            default_value=def_val,
            ordinal_levels=ord_levels,
        )

    @classmethod
    def assemble_variables(
        cls,
        entities: dict[str, PolicyEntity],
        dep_map: dict[str, EntityDependencyLink],
        layer_indices: dict[str, int],
    ) -> dict[str, InferredVariable]:
        variables: dict[str, InferredVariable] = {}
        in_degrees: dict[str, int] = {eid: 0 for eid in entities}
        out_degrees: dict[str, int] = {eid: 0 for eid in entities}

        for link in dep_map.values():
            in_degrees[link.target_canonical_id] = len(link.input_canonical_ids)
            for parent_id in link.input_canonical_ids:
                if parent_id in out_degrees:
                    out_degrees[parent_id] += 1

        for eid, ent in entities.items():
            var = cls._create_variable_from_entity(ent)
            var.in_degree = in_degrees.get(eid, 0)
            var.out_degree = out_degrees.get(eid, 0)
            var.layer_index = layer_indices.get(eid, 0)
            variables[eid] = var

            if ent.role == EntityRole.INPUT or ent.z3_sort == Z3SortType.INT:
                comp_id = f"{eid}_intensity"
                variables[comp_id] = InferredVariable(
                    var_id=comp_id,
                    human_name=f"{ent.original_name} (Intensity)",
                    role=VariableRole.INTERMEDIATE,
                    sort=VariableSort.REAL,
                    min_bound=0.0,
                    max_bound=100.0,
                    default_value=0.0,
                    layer_index=layer_indices.get(eid, 0),
                )
        return variables

    @staticmethod
    def assemble_equations(
        synthesized_rules: dict[str, SynthesizedNodeRule],
        compiler: DeterministicZ3LoweringCompiler,
        entities: dict[str, PolicyEntity],
        dep_map: dict[str, EntityDependencyLink],
    ) -> tuple[dict[str, InferredEquation], list[str]]:
        equations: dict[str, InferredEquation] = {}
        order: list[str] = []

        # Layer 0 input intensities
        for eid, ent in entities.items():
            if ent.role == EntityRole.INPUT:
                comp_id = f"{eid}_intensity"
                raw_ast = compiler.build_default_intensity_ast(ent)
                smt_expr = compiler.to_smt_expression(raw_ast)
                equations[comp_id] = InferredEquation(
                    equation_id=f"eq_{comp_id}",
                    target_var=comp_id,
                    dependencies=[eid],
                    smt_expression=smt_expr,
                    natural_language_logic=f"Foundational risk intensity mapping for {eid}",
                )
                order.append(comp_id)

        # Synthesized derived nodes & companion variables
        for tid, rule in synthesized_rules.items():
            link = dep_map.get(tid)
            deps = list(link.input_canonical_ids) if link else []
            smt_expr = compiler.to_smt_expression(rule.expr_ast)
            equations[tid] = InferredEquation(
                equation_id=f"eq_{tid}",
                target_var=tid,
                dependencies=deps,
                smt_expression=smt_expr,
                natural_language_logic=rule.reasoning_trace,
            )
            order.append(tid)

            ent = entities.get(tid)
            if ent and ent.z3_sort == Z3SortType.INT:
                comp_id = f"{tid}_intensity"
                comp_ast = compiler.extract_continuous_intensity_ast(ent, rule)
                comp_smt = compiler.to_smt_expression(comp_ast)
                equations[comp_id] = InferredEquation(
                    equation_id=f"eq_{comp_id}",
                    target_var=comp_id,
                    dependencies=deps,
                    smt_expression=comp_smt,
                    natural_language_logic=f"Continuous risk intensity for {tid}",
                )
                order.append(comp_id)

        return equations, order

    @classmethod
    def build_graph(
        cls,
        raw_text: str,
        sentence_count: int,
        entities: dict[str, PolicyEntity],
        dep_map: dict[str, EntityDependencyLink],
        synthesized_rules: dict[str, SynthesizedNodeRule],
        compiler: DeterministicZ3LoweringCompiler,
        waves: list[list[str]],
        compiler_log: list[str],
    ) -> AutonomousPolicyGraph:
        layer_indices: dict[str, int] = {}
        for wave_idx, wave_nodes in enumerate(waves):
            for node in wave_nodes:
                layer_indices[node] = wave_idx + 1

        variables = cls.assemble_variables(entities, dep_map, layer_indices)
        equations, top_order = cls.assemble_equations(
            synthesized_rules, compiler, entities, dep_map
        )

        return AutonomousPolicyGraph(
            graph_id=f"graph_{uuid.uuid4().hex[:8]}",
            title="Autoformalized Policy Graph",
            raw_document_text=raw_text,
            sentence_count=sentence_count,
            variables=variables,
            equations=equations,
            topological_order=top_order,
            cegis_compiler_log=compiler_log,
        )

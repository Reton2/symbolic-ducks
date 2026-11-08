from __future__ import annotations

import logging
from typing import Any

from z3 import (
    And,
    Bool,
    BoolVal,
    Implies,
    Int,
    IntVal,
    Optimize,
    Real,
    RealVal,
    Solver,
    is_int_value,
    is_rational_value,
    is_true,
    sat,
)

from app.schemas import (
    AbductiveSolveResult,
    AbductiveSolveStatus,
    AutonomousPolicyGraph,
    ChangedInputSpec,
    ConstraintOperator,
    CounterfactualResult,
    CounterfactualStatus,
    DeadLogicClassification,
    DeadLogicDiagnostic,
    GraphVerificationReport,
    InferredVariable,
    ReachabilityProof,
    SolvedModelWitness,
    TargetConstraintSpec,
    VariableSolvedState,
    VariableSort,
    VerificationStatus,
)
from app.services.smt.smt_helpers import evaluate_z3_symbolic_expression

logger = logging.getLogger(__name__)


class DeepSMTSolverEngine:
    def __init__(
        self,
        graph: AutonomousPolicyGraph,
        param_overrides: dict[str, float] | None = None,
    ) -> None:
        param_overrides = param_overrides or None
        self.graph = graph
        self.param_values: dict[str, float] = {
            k: float(v.default_value)
            for k, v in graph.variables.items()
            if v.role == "PARAMETER"
        }
        if param_overrides:
            self.param_values.update(param_overrides)

        self.z3_vars: dict[str, Real | Int | Bool] = {}
        self._init_z3_vars()

    def _init_z3_vars(self) -> None:
        for vid, v in self.graph.variables.items():
            if v.sort == "real":
                self.z3_vars[vid] = Real(vid)
            elif v.sort == "int":
                self.z3_vars[vid] = Int(vid)
            else:
                self.z3_vars[vid] = Bool(vid)

    def _build_parameter_constraint(self, vid: str, v: InferredVariable) -> Any:
        zvar = self.z3_vars[vid]
        val = self.param_values.get(vid, float(v.default_value))
        if v.sort == "real":
            return zvar == RealVal(float(val))
        if v.sort == "int":
            return zvar == IntVal(int(val))
        return zvar == BoolVal(bool(val))

    def _build_variable_bounds(
        self, vid: str, v: InferredVariable, bind_parameters: bool
    ) -> list[Any]:
        if v.role == "PARAMETER" and bind_parameters:
            return [self._build_parameter_constraint(vid, v)]

        constraints: list[Any] = []
        zvar = self.z3_vars[vid]
        if v.sort in ("real", "int"):
            lower_bound = (
                RealVal(v.min_bound) if v.sort == "real" else IntVal(int(v.min_bound))
            )
            upper_bound = (
                RealVal(v.max_bound) if v.sort == "real" else IntVal(int(v.max_bound))
            )
            constraints.append(zvar >= lower_bound)
            constraints.append(zvar <= upper_bound)
        return constraints

    def _build_base_constraints(self, bind_parameters: bool = True) -> list[Any]:
        constraints: list[Any] = []
        for vid, v in self.graph.variables.items():
            constraints.extend(self._build_variable_bounds(vid, v, bind_parameters))

        for target_id in self.graph.topological_order:
            if target_id in self.graph.equations:
                eq = self.graph.equations[target_id]
                rhs_z3 = evaluate_z3_symbolic_expression(
                    eq.smt_expression, self.z3_vars
                )
                constraints.append(self.z3_vars[target_id] == rhs_z3)
        return constraints

    @staticmethod
    def _parse_model_value(
        m_val: Any, sort: str, default_val: float | int | bool
    ) -> float | int | bool:
        if m_val is None:
            return default_val
        if is_rational_value(m_val):
            return round(
                float(m_val.numerator_as_long()) / float(m_val.denominator_as_long()), 2
            )
        if is_int_value(m_val):
            return int(m_val.as_long())
        if sort == "bool":
            return bool(is_true(m_val))
        return default_val

    def _extract_model(self, model: Any) -> SolvedModelWitness:
        witness = SolvedModelWitness()
        for vid, v in self.graph.variables.items():
            m_val = model[self.z3_vars[vid]]
            parsed = self._parse_model_value(m_val, v.sort, v.default_value)
            label = (
                v.ordinal_levels.get(int(parsed), str(parsed))
                if (v.ordinal_levels and isinstance(parsed, (int, float)))
                else str(parsed)
            )
            formatted = f"{parsed} ({label})" if v.ordinal_levels else str(parsed)
            state_item = VariableSolvedState(
                human_name=v.human_name,
                value=parsed,
                formatted=formatted,
                layer=v.layer_index,
            )
            getattr(witness, v.role)[vid] = state_item
        return witness

    def export_smtlib2(self) -> str:
        s = Solver()
        s.add(*self._build_base_constraints(bind_parameters=True))
        return s.to_smt2()

    def diagnose_unreachable_state(
        self,
        out_v: InferredVariable,
        target_cond: Any,
        target_state_label: str,
    ) -> DeadLogicDiagnostic:
        # Step 1: Parameter Relaxation Check
        relaxed_base = self._build_base_constraints(bind_parameters=False)
        relaxed_solver = Solver()
        relaxed_solver.add(*relaxed_base)
        relaxed_solver.add(target_cond)

        if relaxed_solver.check() == sat:
            m = relaxed_solver.model()
            param_fixes: dict[str, float] = {}
            for pid, pvar in self.graph.variables.items():
                if pvar.role == "PARAMETER" and pid in self.z3_vars:
                    val = self._parse_model_value(
                        m[self.z3_vars[pid]], pvar.sort, pvar.default_value
                    )
                    curr = self.param_values.get(pid, float(pvar.default_value))
                    if (
                        isinstance(val, (int, float))
                        and abs(float(val) - float(curr)) > 1e-4
                    ):
                        param_fixes[pid] = float(val)

            fixes_str = ", ".join(
                f"{k}: {self.param_values.get(k, 0)} -> {v}"
                for k, v in list(param_fixes.items())[:3]
            )
            return DeadLogicDiagnostic(
                target_variable=out_v.var_id,
                human_name=out_v.human_name,
                target_state=target_state_label,
                classification=DeadLogicClassification.PARAMETER_MISCALIBRATION,
                explanation=(
                    f"'{out_v.human_name}' can reach state '{target_state_label}', but active parameter thresholds "
                    f"exclude this path. The underlying DAG equations and policy structure are sound."
                ),
                suggested_remediation=(
                    f"Recalibrate parameter thresholds. Feasible parameters exist: {fixes_str}"
                    if param_fixes
                    else "Adjust bound thresholds on upstream parameter variables."
                ),
                relaxed_parameter_solutions=param_fixes,
            )

        # Step 2: Unsat Core Extraction with Tracked Assumption Literals
        tracked_solver = Solver()
        assumptions: list[Any] = []
        track_map: dict[str, tuple[str, str, list[int]]] = {}

        for target_id in self.graph.topological_order:
            if target_id in self.graph.equations:
                eq = self.graph.equations[target_id]
                rhs_z3 = evaluate_z3_symbolic_expression(
                    eq.smt_expression, self.z3_vars
                )
                t_lit = Bool(f"track_eq_{target_id}")
                tracked_solver.add(Implies(t_lit, self.z3_vars[target_id] == rhs_z3))
                assumptions.append(t_lit)
                track_map[str(t_lit)] = ("EQUATION", target_id, eq.source_sentence_ids)

        for vid, v in self.graph.variables.items():
            if v.sort in ("real", "int"):
                b_lit = Bool(f"track_bnd_{vid}")
                zvar = self.z3_vars[vid]
                lower = (
                    RealVal(v.min_bound)
                    if v.sort == "real"
                    else IntVal(int(v.min_bound))
                )
                upper = (
                    RealVal(v.max_bound)
                    if v.sort == "real"
                    else IntVal(int(v.max_bound))
                )
                tracked_solver.add(Implies(b_lit, And(zvar >= lower, zvar <= upper)))
                assumptions.append(b_lit)
                track_map[str(b_lit)] = ("BOUND", vid, v.source_sentence_ids)

        tgt_lit = Bool("track_target_directive")
        tracked_solver.add(Implies(tgt_lit, target_cond))
        assumptions.append(tgt_lit)

        tracked_solver.check(assumptions)
        core = tracked_solver.unsat_core()
        core_names = [str(c) for c in core]

        conflicting_eqs: list[str] = []
        conflicting_sentences: list[int] = []

        for c_name in core_names:
            if c_name in track_map:
                kind, item_id, s_ids = track_map[c_name]
                if kind == "EQUATION":
                    conflicting_eqs.append(item_id)
                for sid in s_ids:
                    if sid not in conflicting_sentences:
                        conflicting_sentences.append(sid)

        sentence_texts: list[str] = []
        raw_doc = self.graph.raw_document_text
        if raw_doc:
            doc_lines = [line.strip() for line in raw_doc.split("\n") if line.strip()]
            for sid in conflicting_sentences:
                if 0 <= sid < len(doc_lines):
                    sentence_texts.append(f"[Sentence {sid}] {doc_lines[sid]}")

        # Step 3: Classify Wrong Rule vs Wrong Policy
        if len(conflicting_eqs) <= 1:
            eq_target = conflicting_eqs[0] if conflicting_eqs else out_v.var_id
            return DeadLogicDiagnostic(
                target_variable=out_v.var_id,
                human_name=out_v.human_name,
                target_state=target_state_label,
                classification=DeadLogicClassification.WRONG_RULE_COMPILER,
                explanation=(
                    f"Equation for '{eq_target}' contains an internal mathematical or sort contradiction. "
                    f"Even with all parameters unrestricted, state '{target_state_label}' is mathematically unsatisfiable."
                ),
                conflicting_equation_ids=conflicting_eqs,
                conflicting_sentence_ids=conflicting_sentences,
                conflicting_sentences_text=sentence_texts,
                suggested_remediation=(
                    f"Autoformalization error detected in equation '{eq_target}'. Re-synthesize formula or check "
                    f"relational operator directions (< vs >) and sort casting."
                ),
            )
        else:
            return DeadLogicDiagnostic(
                target_variable=out_v.var_id,
                human_name=out_v.human_name,
                target_state=target_state_label,
                classification=DeadLogicClassification.WRONG_POLICY_MANDATE,
                explanation=(
                    f"Cross-clause policy contradiction between equations [{', '.join(conflicting_eqs)}]. "
                    f"The simultaneous mandates of clauses {conflicting_sentences} cannot be reconciled in any market state."
                ),
                conflicting_equation_ids=conflicting_eqs,
                conflicting_sentence_ids=conflicting_sentences,
                conflicting_sentences_text=sentence_texts,
                suggested_remediation=(
                    f"Contradictory policy mandates identified in source text (Clauses {conflicting_sentences}). "
                    f"Submit policy governance update to reconcile conflicting requirements."
                ),
            )

    def _verify_ordinal_reachability(
        self, out_v: InferredVariable, base_constraints: list[Any]
    ) -> tuple[list[ReachabilityProof], list[str]]:
        proofs: list[ReachabilityProof] = []
        warnings: list[str] = []
        zvar = self.z3_vars[out_v.var_id]

        assert out_v.ordinal_levels is not None
        for tier_int, tier_label in out_v.ordinal_levels.items():
            target_cond = zvar == IntVal(int(tier_int))
            solver = Solver()
            solver.add(*base_constraints)
            solver.add(target_cond)
            can_reach = solver.check() == sat
            diag = None
            if not can_reach:
                diag = self.diagnose_unreachable_state(
                    out_v, target_cond, f"{tier_int} ({tier_label})"
                )
                warnings.append(
                    f"{out_v.human_name} cannot ever reach state '{tier_label}' "
                    f"({tier_int}) under current parameter settings. [Cause: {diag.classification}]"
                )
            proofs.append(
                ReachabilityProof(
                    output_var=out_v.var_id,
                    human_name=out_v.human_name,
                    target_state=f"{tier_int} ({tier_label})",
                    reachable=can_reach,
                    diagnostic=diag,
                )
            )
        return proofs, warnings

    def _verify_continuous_reachability(
        self, out_v: InferredVariable, base_constraints: list[Any]
    ) -> tuple[list[ReachabilityProof], list[str]]:
        proofs: list[ReachabilityProof] = []
        warnings: list[str] = []
        zvar = self.z3_vars[out_v.var_id]

        continuous_targets = [
            ("Low Allocation (<=20%)", zvar <= RealVal(20.0)),
            ("High Allocation (>=80%)", zvar >= RealVal(80.0)),
        ]
        for label, cond in continuous_targets:
            solver = Solver()
            solver.add(*base_constraints)
            solver.add(cond)
            can_reach = solver.check() == sat
            diag = None
            if not can_reach:
                diag = self.diagnose_unreachable_state(out_v, cond, label)
                warnings.append(
                    f"{out_v.human_name} cannot ever reach '{label}' under current parameters. [Cause: {diag.classification}]"
                )
            proofs.append(
                ReachabilityProof(
                    output_var=out_v.var_id,
                    human_name=out_v.human_name,
                    target_state=label,
                    reachable=can_reach,
                    diagnostic=diag,
                )
            )
        return proofs, warnings

    def verify_full_graph(self) -> GraphVerificationReport:
        """Proves satisfiability of the policy DAG and checks reachability of all output directives."""
        logger.info("Executing Z3 policy graph verification (SAT & Reachability)...")
        base = self._build_base_constraints(bind_parameters=True)
        s = Solver()
        s.add(*base)
        is_consistent = s.check() == sat

        proofs: list[ReachabilityProof] = []
        dead_states: list[str] = []
        outputs = [v for v in self.graph.variables.values() if v.role == "OUTPUT"]

        for out_v in outputs:
            if out_v.ordinal_levels:
                p, w = self._verify_ordinal_reachability(out_v, base)
            else:
                p, w = self._verify_continuous_reachability(out_v, base)
            proofs.extend(p)
            dead_states.extend(w)

        report_status = (
            VerificationStatus.VERIFIED
            if (is_consistent and not dead_states)
            else VerificationStatus.DEAD_LOGIC_DETECTED
        )
        logger.info(
            "Formal verification status: %s (consistent=%s, dead_states=%d)",
            report_status,
            is_consistent,
            len(dead_states),
        )
        reachable_count = sum(1 for p in proofs if p.reachable)
        dead_count = sum(1 for p in proofs if not p.reachable)
        return GraphVerificationReport(
            status=report_status,
            consistent=is_consistent,
            is_dag_consistent=is_consistent,
            reachable_count=reachable_count,
            dead_count=dead_count,
            dead_state_warnings=dead_states,
            reachability_proofs=proofs,
        )

    def _apply_single_target(
        self, vid: str, op: str | ConstraintOperator, raw_val: Any, solver: Solver
    ) -> str:
        v_info = self.graph.variables[vid]
        zvar = self.z3_vars[vid]
        if v_info.sort == VariableSort.REAL:
            zval: Any = RealVal(float(raw_val))
        elif v_info.sort == VariableSort.INT:
            target_int: int | None = None
            if v_info.ordinal_levels:
                raw_str = str(raw_val).strip()
                for idx, lvl_name in v_info.ordinal_levels.items():
                    if (
                        str(lvl_name).strip().upper() == raw_str.upper()
                        or str(idx) == raw_str
                    ):
                        target_int = int(idx)
                        break
            if target_int is None:
                target_int = int(float(raw_val))
            zval = IntVal(target_int)
        else:
            target_bool = str(raw_val).strip().lower() in ("true", "1", "sat", "t")
            zval = BoolVal(target_bool)

        op_str = str(op)
        if op_str in (ConstraintOperator.EQ, "=="):
            solver.add(zvar == zval)
        elif op_str in (ConstraintOperator.NE, "!="):
            solver.add(zvar != zval)
        elif op_str in (ConstraintOperator.GT, ">"):
            solver.add(zvar > zval)
        elif op_str in (ConstraintOperator.GTE, ">="):
            solver.add(zvar >= zval)
        elif op_str in (ConstraintOperator.LT, "<"):
            solver.add(zvar < zval)
        elif op_str in (ConstraintOperator.LTE, "<="):
            solver.add(zvar <= zval)
        return f"{v_info.human_name} {op_str} {raw_val}"

    def solve_for_inputs(
        self,
        target_constraints: (
            dict[str, TargetConstraintSpec] | dict[str, dict[str, Any]]
        ),
    ) -> AbductiveSolveResult:
        """Solves backwards from desired output/intermediate states to primary input variables."""
        logger.info(
            "Executing abductive solve for %d target constraints...",
            len(target_constraints),
        )
        s = Solver()
        s.add(*self._build_base_constraints(bind_parameters=True))

        applied: list[str] = []
        for vid, raw_spec in target_constraints.items():
            if vid not in self.z3_vars:
                continue
            spec = (
                raw_spec
                if isinstance(raw_spec, TargetConstraintSpec)
                else TargetConstraintSpec.model_validate(raw_spec)
            )
            applied_str = self._apply_single_target(vid, spec.op, spec.val, s)
            applied.append(applied_str)

        if s.check() == sat:
            witness = self._extract_model(s.model())
            logger.info("Abductive solver found SAT model witness for applied targets")
            return AbductiveSolveResult(
                status=AbductiveSolveStatus.SATISFIABLE,
                applied_targets=applied,
                solved_state=witness,
            )

        logger.warning("Abductive solver returned UNSAT for constraints: %s", applied)
        return AbductiveSolveResult(
            status=AbductiveSolveStatus.UNSATISFIABLE,
            applied_targets=applied,
            message="Z3 proved UNSAT: No combination of primary inputs satisfies these constraints.",
        )

    def _diff_counterfactual_inputs(
        self,
        witness: SolvedModelWitness,
        current_inputs: dict[str, float],
    ) -> dict[str, ChangedInputSpec]:
        changes: dict[str, ChangedInputSpec] = {}
        for vid, solved_info in witness.INPUT.items():
            old_v = current_inputs.get(vid, self.graph.variables[vid].default_value)
            if abs(float(solved_info.value) - float(old_v)) > 1e-4:
                changes[vid] = ChangedInputSpec(
                    human_name=solved_info.human_name,
                    previous_value=old_v,
                    required_value=solved_info.formatted,
                )
        return changes

    def solve_counterfactual_repair(
        self,
        current_inputs: dict[str, float],
        desired_output_var: str,
        desired_val: float,
    ) -> CounterfactualResult:
        """Finds minimal primary input adjustments to achieve desired target directive."""
        logger.info(
            "Running MaxSMT counterfactual search for %s -> %s...",
            desired_output_var,
            desired_val,
        )
        opt = Optimize()
        opt.add(*self._build_base_constraints(bind_parameters=True))

        if desired_output_var in self.z3_vars:
            v_out = self.graph.variables[desired_output_var]
            zval = (
                RealVal(float(desired_val))
                if v_out.sort == "real"
                else IntVal(int(desired_val))
            )
            opt.add(self.z3_vars[desired_output_var] == zval)

        for vid, v in self.graph.variables.items():
            if v.role == "INPUT" and vid in current_inputs:
                curr = current_inputs[vid]
                zval_curr = (
                    RealVal(float(curr)) if v.sort == "real" else IntVal(int(curr))
                )
                opt.add_soft(self.z3_vars[vid] == zval_curr, weight=10)

        if opt.check() == sat:
            witness = self._extract_model(opt.model())
            changes = self._diff_counterfactual_inputs(witness, current_inputs)
            logger.info(
                "Counterfactual repair found: %d input modifications", len(changes)
            )
            return CounterfactualResult(
                status=CounterfactualStatus.COUNTERFACTUAL_FOUND,
                minimal_input_changes_count=len(changes),
                changed_inputs=changes,
                resulting_outputs=witness.OUTPUT,
            )

        logger.warning(
            "Counterfactual repair UNSAT: Target state %s=%s unreachable",
            desired_output_var,
            desired_val,
        )
        return CounterfactualResult(
            status=CounterfactualStatus.UNSAT,
            message="Target output state is unreachable.",
        )

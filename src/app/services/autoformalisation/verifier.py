from __future__ import annotations

import z3

from app.services.autoformalisation.compiler import DeterministicZ3LoweringCompiler
from app.services.autoformalisation.models import (
    EmpiricalTestCase,
    EntityRole,
    PolicyEntity,
    SynthesizedNodeRule,
    Z3SortType,
)
from app.services.autoformalisation.sanitization import to_canonical_identifier


class Z3VerificationSandbox:
    """SMT verification sandbox executing safety, reachability, and test checks."""

    def __init__(
        self,
        entities: dict[str, PolicyEntity],
        compiler: DeterministicZ3LoweringCompiler,
    ) -> None:
        self.entities = entities
        self.compiler = compiler
        self.z3_vars: dict[str, z3.ExprRef] = {}
        self.domain_constraints: list[z3.ExprRef] = []
        self._init_variables()

    def _init_variables(self) -> None:
        for eid, ent in self.entities.items():
            if ent.z3_sort == Z3SortType.REAL:
                v = z3.Real(eid)
                self.z3_vars[eid] = v
                if ent.role == EntityRole.INPUT:
                    self.domain_constraints.append(v >= z3.RealVal(ent.min_bound))
                    self.domain_constraints.append(v <= z3.RealVal(ent.max_bound))
            else:
                v = z3.Int(eid)
                self.z3_vars[eid] = v
                if ent.role == EntityRole.INPUT:
                    self.domain_constraints.append(v >= z3.IntVal(int(ent.min_bound)))
                    self.domain_constraints.append(v <= z3.IntVal(int(ent.max_bound)))

            if ent.role == EntityRole.INPUT or ent.z3_sort == Z3SortType.INT:
                comp_id = f"{eid}_intensity"
                comp_v = z3.Real(comp_id)
                self.z3_vars[comp_id] = comp_v
                self.domain_constraints.append(comp_v >= z3.RealVal(0.0))
                self.domain_constraints.append(comp_v <= z3.RealVal(100.0))

    def _check_sat(
        self, base_assertions: list[z3.ExprRef], target_id: str
    ) -> str | None:
        solver = z3.Solver()
        solver.add(*base_assertions)
        if solver.check() != z3.sat:
            return f"Logical Contradiction: Adding constraint for '{target_id}' renders the system UNSAT."
        return None

    def _check_bounds(
        self,
        base_assertions: list[z3.ExprRef],
        target_ent: PolicyEntity,
        target_var: z3.ExprRef,
        cont_z3: z3.ExprRef | None,
    ) -> list[str]:
        diagnostics: list[str] = []
        oob_solver = z3.Solver()
        oob_solver.add(*base_assertions)
        if target_ent.z3_sort == Z3SortType.REAL:
            oob_solver.add(
                z3.Or(
                    target_var < z3.RealVal(target_ent.min_bound),
                    target_var > z3.RealVal(target_ent.max_bound),
                )
            )
        else:
            oob_solver.add(
                z3.Or(
                    target_var < z3.IntVal(int(target_ent.min_bound)),
                    target_var > z3.IntVal(int(target_ent.max_bound)),
                )
            )
        if oob_solver.check() == z3.sat:
            bad_val = oob_solver.model().evaluate(target_var)
            diagnostics.append(
                f"Bound Violation: '{target_ent.canonical_id}' can evaluate to {bad_val}, outside "
                f"[{target_ent.min_bound}, {target_ent.max_bound}]."
            )
        if cont_z3 is not None:
            cont_solver = z3.Solver()
            cont_solver.add(*base_assertions)
            cont_solver.add(
                z3.Or(cont_z3 < z3.RealVal(0.0), cont_z3 > z3.RealVal(100.0))
            )
            if cont_solver.check() == z3.sat:
                bad_c = cont_solver.model().evaluate(cont_z3)
                diagnostics.append(
                    f"Continuous Intensity Bound Violation: '{target_ent.canonical_id}' intensity "
                    f"evaluates to {bad_c}, outside [0.0, 100.0]."
                )
        return diagnostics

    def _check_reachability(
        self,
        base_assertions: list[z3.ExprRef],
        target_ent: PolicyEntity,
        target_var: z3.ExprRef,
    ) -> list[str]:
        diagnostics: list[str] = []
        if target_ent.z3_sort == Z3SortType.INT:
            unreachable: list[int] = []
            for k in range(int(target_ent.min_bound), int(target_ent.max_bound) + 1):
                st_solver = z3.Solver()
                st_solver.add(*base_assertions)
                st_solver.add(target_var == z3.IntVal(k))
                if st_solver.check() != z3.sat:
                    unreachable.append(k)
            if unreachable:
                diagnostics.append(
                    f"Dead Logic: Discrete target '{target_ent.canonical_id}' cannot reach state(s) {unreachable}."
                )
        else:
            s1 = z3.Solver()
            s1.add(*base_assertions)
            if s1.check() == z3.sat:
                first_val = s1.model().evaluate(target_var)
                s2 = z3.Solver()
                s2.add(*base_assertions)
                s2.add(target_var != first_val)
                if s2.check() != z3.sat:
                    diagnostics.append(
                        f"Constant Logic Error: Continuous target '{target_ent.canonical_id}' is permanently stuck at {first_val}."
                    )
        return diagnostics

    def _check_single_test_case(
        self,
        base_assertions: list[z3.ExprRef],
        target_ent: PolicyEntity,
        target_var: z3.ExprRef,
        tc: EmpiricalTestCase,
    ) -> str | None:
        tc_solver = z3.Solver()
        tc_solver.add(*base_assertions)
        for inp_id, inp_val in tc.input_assignments.items():
            cid = to_canonical_identifier(inp_id)
            if cid not in self.z3_vars:
                continue
            inp_var = self.z3_vars[cid]
            val = (
                z3.RealVal(float(inp_val))
                if z3.is_real(inp_var)
                else z3.IntVal(int(inp_val))
            )
            tc_solver.add(inp_var == val)

        if tc_solver.check() != z3.sat:
            return (
                f"Empirical Test Contradiction ('{tc.description}'): Input assignments "
                f"{tc.input_assignments} are UNSATISFIABLE given upstream DAG constraints."
            )
        actual = tc_solver.model().evaluate(target_var)
        expected = (
            z3.RealVal(float(tc.expected_target_value))
            if target_ent.z3_sort == Z3SortType.REAL
            else z3.IntVal(int(tc.expected_target_value))
        )
        check_diff = z3.Solver()
        if target_ent.z3_sort == Z3SortType.REAL:
            check_diff.add(z3.Abs(actual - expected) > z3.RealVal(0.05))
        else:
            check_diff.add(actual != expected)
        if check_diff.check() == z3.sat:
            return (
                f"Empirical Test Failed ('{tc.description}'): With inputs {tc.input_assignments}, "
                f"AST evaluated to {actual} instead of expected {tc.expected_target_value}."
            )
        return None

    def verify_node_rule(
        self,
        target_id: str,
        rule: SynthesizedNodeRule,
        prior_constraints: dict[str, z3.ExprRef],
    ) -> tuple[bool, list[str], z3.ExprRef | None]:
        """Formally verifies candidate SynthesizedNodeRule against DAG assertions."""
        target_ent = self.entities[target_id]
        target_var = self.z3_vars[target_id]
        try:
            rhs_z3 = self.compiler.to_z3_expr(
                rule.expr_ast, self.z3_vars, expected_sort=target_ent.z3_sort
            )
            eq_constraint = target_var == rhs_z3
            cont_z3 = (
                self.compiler.to_z3_expr(
                    rule.continuous_intensity_ast,
                    self.z3_vars,
                    expected_sort=Z3SortType.REAL,
                )
                if rule.continuous_intensity_ast is not None
                else None
            )
        except Exception as exc:
            return False, [f"Z3 Compilation / Sort Error: {exc}"], None

        base = (
            self.domain_constraints + list(prior_constraints.values()) + [eq_constraint]
        )
        sat_err = self._check_sat(base, target_id)
        if sat_err:
            return False, [sat_err], None

        diagnostics: list[str] = []
        diagnostics.extend(self._check_bounds(base, target_ent, target_var, cont_z3))
        diagnostics.extend(self._check_reachability(base, target_ent, target_var))

        for tc in rule.test_cases:
            tc_err = self._check_single_test_case(base, target_ent, target_var, tc)
            if tc_err:
                diagnostics.append(tc_err)

        return (len(diagnostics) == 0), diagnostics, eq_constraint

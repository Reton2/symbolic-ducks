from __future__ import annotations

from typing import Literal

import z3

from app.services.autoformalisation.models import (
    DiscreteStateMapping,
    EntityRole,
    LogicExpr,
    Modality,
    NumericalThresholdMapping,
    PolicyEntity,
    SynthesizedNodeRule,
    Z3SortType,
)
from app.services.autoformalisation.sanitization import to_canonical_identifier


class DeterministicZ3LoweringCompiler:
    """Lowers typed LogicExpr ASTs into executable Z3 ExprRef objects and SMT strings."""

    def __init__(self, entities: dict[str, PolicyEntity]) -> None:
        self.entities = entities
        self.intensity_ast_cache: dict[str, LogicExpr] = {}
        for eid, ent in self.entities.items():
            if ent.role == EntityRole.INPUT:
                self.intensity_ast_cache[eid] = LogicExpr(
                    kind="var_ref", var_id=f"{eid}_intensity"
                )
            elif ent.z3_sort == Z3SortType.REAL:
                self.intensity_ast_cache[eid] = LogicExpr(kind="var_ref", var_id=eid)
            else:
                self.intensity_ast_cache[eid] = LogicExpr(
                    kind="var_ref", var_id=f"{eid}_intensity"
                )

    def _build_discrete_intensity_ast(
        self, eid: str, states: list[DiscreteStateMapping]
    ) -> LogicExpr:
        """Builds an ITE ladder for discrete ordinal or categorical states."""
        sorted_states = sorted(states, key=lambda s: s.state_index, reverse=True)
        if not sorted_states:
            return LogicExpr(kind="literal_real", float_val=0.0)
        if len(sorted_states) == 1:
            return LogicExpr(
                kind="literal_real", float_val=float(sorted_states[0].intensity_score)
            )

        expr = LogicExpr(
            kind="literal_real", float_val=float(sorted_states[-1].intensity_score)
        )
        for state in sorted_states[:-1][::-1]:
            cond = LogicExpr(
                kind="compare",
                comp_op="==",
                left=LogicExpr(kind="var_ref", var_id=eid),
                right=LogicExpr(kind="literal_int", int_val=int(state.state_index)),
            )
            expr = LogicExpr(
                kind="ite",
                cond=cond,
                then_branch=LogicExpr(
                    kind="literal_real", float_val=float(state.intensity_score)
                ),
                else_branch=expr,
            )
        return expr

    def _build_numerical_intensity_ast(
        self, eid: str, sort: Z3SortType, nm: NumericalThresholdMapping
    ) -> LogicExpr:
        """Builds threshold comparison ITE for numerical inputs."""
        right_lit = (
            LogicExpr(kind="literal_int", int_val=int(nm.threshold_value))
            if sort == Z3SortType.INT
            else LogicExpr(kind="literal_real", float_val=float(nm.threshold_value))
        )
        cond = LogicExpr(
            kind="compare",
            comp_op=nm.comparison_op,
            left=LogicExpr(kind="var_ref", var_id=eid),
            right=right_lit,
        )
        return LogicExpr(
            kind="ite",
            cond=cond,
            then_branch=LogicExpr(
                kind="literal_real", float_val=float(nm.breach_intensity)
            ),
            else_branch=LogicExpr(
                kind="literal_real", float_val=float(nm.baseline_intensity)
            ),
        )

    def build_default_intensity_ast(self, ent: PolicyEntity) -> LogicExpr:
        """Constructs unified 0..100 intensity AST for any entity metadata."""
        if ent.modality in (Modality.ORDINAL, Modality.CATEGORICAL):
            return self._build_discrete_intensity_ast(
                ent.canonical_id, ent.discrete_states
            )
        if ent.modality == Modality.NUMERICAL and ent.numerical_mapping is not None:
            return self._build_numerical_intensity_ast(
                ent.canonical_id, ent.z3_sort, ent.numerical_mapping
            )
        return LogicExpr(kind="var_ref", var_id=ent.canonical_id)

    def extract_continuous_intensity_ast(
        self, ent: PolicyEntity, rule: SynthesizedNodeRule
    ) -> LogicExpr:
        """Resolves continuous intensity expression for discrete intermediate nodes."""
        if rule.continuous_intensity_ast is not None:
            return rule.continuous_intensity_ast
        if ent.z3_sort == Z3SortType.REAL:
            return LogicExpr(kind="var_ref", var_id=ent.canonical_id)

        root = rule.expr_ast
        if root.kind == "ite" and root.cond is not None and root.cond.kind == "compare":
            for side in (root.cond.left, root.cond.right):
                if side is not None and side.kind in (
                    "min_pool",
                    "max_pool",
                    "complement_100",
                    "var_intensity",
                ):
                    return side
        return self.build_default_intensity_ast(ent)

    def _build_balanced_minmax_ite(
        self, items: list[LogicExpr], is_min: bool
    ) -> LogicExpr:
        """Builds a balanced binary ITE tree for min/max without helper variables."""
        if len(items) == 1:
            return items[0]
        if len(items) == 2:
            a, b = items[0], items[1]
            op: Literal["<=", ">="] = "<=" if is_min else ">="
            return LogicExpr(
                kind="ite",
                cond=LogicExpr(kind="compare", comp_op=op, left=a, right=b),
                then_branch=a,
                else_branch=b,
            )
        mid = len(items) // 2
        left_branch = self._build_balanced_minmax_ite(items[:mid], is_min=is_min)
        right_branch = self._build_balanced_minmax_ite(items[mid:], is_min=is_min)
        return self._build_balanced_minmax_ite(
            [left_branch, right_branch], is_min=is_min
        )

    def expand_high_level_nodes(self, expr: LogicExpr) -> LogicExpr:
        """Recursively lowers var_intensity, min_pool, and max_pool into primitive ITEs."""
        k = expr.kind
        if k in ("literal_real", "literal_int", "var_ref"):
            return expr
        if k == "var_intensity":
            vid = to_canonical_identifier(expr.var_id or "")
            base = self.intensity_ast_cache.get(
                vid, LogicExpr(kind="var_ref", var_id=vid)
            )
            lowered = self.expand_high_level_nodes(base)
            return (
                LogicExpr(kind="complement_100", left=lowered)
                if expr.invert_intensity
                else lowered
            )
        if k == "complement_100":
            return LogicExpr(
                kind="complement_100",
                left=self.expand_high_level_nodes(
                    expr.left or LogicExpr(kind="literal_real")
                ),
            )
        if k == "not_op":
            return LogicExpr(
                kind="not_op",
                left=self.expand_high_level_nodes(
                    expr.left or LogicExpr(kind="literal_int")
                ),
            )
        if k == "compare":
            return LogicExpr(
                kind="compare",
                comp_op=expr.comp_op,
                left=self.expand_high_level_nodes(
                    expr.left or LogicExpr(kind="literal_real")
                ),
                right=self.expand_high_level_nodes(
                    expr.right or LogicExpr(kind="literal_real")
                ),
            )
        if k in ("and_op", "or_op"):
            expanded_args = [self.expand_high_level_nodes(a) for a in (expr.args or [])]
            if not expanded_args:
                return LogicExpr(kind="literal_int", int_val=1)
            if len(expanded_args) == 1:
                return expanded_args[0]
            return LogicExpr(kind=k, args=expanded_args)
        if k == "ite":
            return LogicExpr(
                kind="ite",
                cond=self.expand_high_level_nodes(
                    expr.cond or LogicExpr(kind="literal_int")
                ),
                then_branch=self.expand_high_level_nodes(
                    expr.then_branch or LogicExpr(kind="literal_real")
                ),
                else_branch=self.expand_high_level_nodes(
                    expr.else_branch or LogicExpr(kind="literal_real")
                ),
            )
        if k in ("min_pool", "max_pool"):
            expanded = [self.expand_high_level_nodes(a) for a in (expr.args or [])]
            if not expanded:
                return LogicExpr(kind="literal_real", float_val=0.0)
            return self._build_balanced_minmax_ite(expanded, is_min=(k == "min_pool"))
        raise ValueError(f"Unsupported LogicExpr kind: {k}")

    def to_python_code(self, expr: LogicExpr) -> str:
        """Renders expanded LogicExpr AST into Python code with variable identifiers."""
        expanded = self.expand_high_level_nodes(expr)
        return self._emit_code(expanded, use_v_dict=False)

    def to_smt_expression(self, expr: LogicExpr) -> str:
        """Renders expanded LogicExpr AST into canonical v['var_id'] SMT string."""
        expanded = self.expand_high_level_nodes(expr)
        return self._emit_code(expanded, use_v_dict=True)

    def _emit_code(self, node: LogicExpr, use_v_dict: bool) -> str:
        k = node.kind
        if k == "literal_real":
            val = float(node.float_val if node.float_val is not None else 0.0)
            return (
                f"{val:.2f}".rstrip("0").rstrip(".")
                if "." in f"{val}"
                else f"{val:.1f}"
            )
        if k == "literal_int":
            return str(int(node.int_val if node.int_val is not None else 0))
        if k == "var_ref":
            vid = to_canonical_identifier(node.var_id or "")
            return f"v['{vid}']" if use_v_dict else vid
        if k == "complement_100":
            return f"(100.0 - {self._emit_code(node.left or LogicExpr(kind='literal_real'), use_v_dict)})"
        if k == "not_op":
            return f"Not({self._emit_code(node.left or LogicExpr(kind='literal_int'), use_v_dict)})"
        if k == "compare":
            left_str = self._emit_code(
                node.left or LogicExpr(kind="literal_real"), use_v_dict
            )
            right_str = self._emit_code(
                node.right or LogicExpr(kind="literal_real"), use_v_dict
            )
            return f"({left_str} {node.comp_op} {right_str})"
        if k in ("and_op", "or_op"):
            op_name = "And" if k == "and_op" else "Or"
            inner = ", ".join(self._emit_code(a, use_v_dict) for a in (node.args or []))
            return f"{op_name}({inner})"
        if k == "ite":
            c = self._emit_code(node.cond or LogicExpr(kind="literal_int"), use_v_dict)
            t = self._emit_code(
                node.then_branch or LogicExpr(kind="literal_real"), use_v_dict
            )
            e = self._emit_code(
                node.else_branch or LogicExpr(kind="literal_real"), use_v_dict
            )
            return f"If({c}, {t}, {e})"
        raise ValueError(f"Unexpanded node in code emitter: {k}")

    def to_z3_expr(
        self,
        expr: LogicExpr,
        z3_vars: dict[str, z3.ExprRef],
        expected_sort: Z3SortType | None = None,
    ) -> z3.ExprRef:
        """Compiles LogicExpr AST directly into live Z3 ExprRef with sort coercion."""
        expanded = self.expand_high_level_nodes(expr)
        res = self._eval_z3(expanded, z3_vars)
        if expected_sort == Z3SortType.REAL and z3.is_int(res):
            return z3.ToReal(res)
        if expected_sort == Z3SortType.INT and z3.is_real(res):
            return z3.ToInt(res)
        return res

    def _eval_z3(self, node: LogicExpr, z3_vars: dict[str, z3.ExprRef]) -> z3.ExprRef:
        k = node.kind
        if k == "literal_real":
            return z3.RealVal(
                float(node.float_val if node.float_val is not None else 0.0)
            )
        if k == "literal_int":
            return z3.IntVal(int(node.int_val if node.int_val is not None else 0))
        if k == "var_ref":
            vid = to_canonical_identifier(node.var_id or "")
            if vid not in z3_vars:
                raise KeyError(
                    f"Unknown variable identifier '{vid}' referenced in AST."
                )
            return z3_vars[vid]
        if k == "complement_100":
            inner = self._eval_z3(node.left or LogicExpr(kind="literal_real"), z3_vars)
            return z3.RealVal(100.0) - (z3.ToReal(inner) if z3.is_int(inner) else inner)
        if k == "not_op":
            return z3.Not(
                self._eval_z3(node.left or LogicExpr(kind="literal_int"), z3_vars)
            )
        if k == "compare":
            return self._eval_z3_compare(node, z3_vars)
        if k == "and_op":
            return z3.And(*[self._eval_z3(a, z3_vars) for a in (node.args or [])])
        if k == "or_op":
            return z3.Or(*[self._eval_z3(a, z3_vars) for a in (node.args or [])])
        if k == "ite":
            return self._eval_z3_ite(node, z3_vars)
        raise ValueError(f"Unhandled Z3 evaluation node: {k}")

    def _eval_z3_compare(
        self, node: LogicExpr, z3_vars: dict[str, z3.ExprRef]
    ) -> z3.ExprRef:
        lhs = self._eval_z3(node.left or LogicExpr(kind="literal_real"), z3_vars)
        rhs = self._eval_z3(node.right or LogicExpr(kind="literal_real"), z3_vars)
        if z3.is_real(lhs) and z3.is_int(rhs):
            rhs = z3.ToReal(rhs)
        elif z3.is_int(lhs) and z3.is_real(rhs):
            lhs = z3.ToReal(lhs)
        op = node.comp_op
        if op == "==":
            return lhs == rhs
        if op == "!=":
            return lhs != rhs
        if op == "<":
            return lhs < rhs
        if op == "<=":
            return lhs <= rhs
        if op == ">":
            return lhs > rhs
        if op == ">=":
            return lhs >= rhs
        raise ValueError(f"Unknown comparison operator {op}")

    def _eval_z3_ite(
        self, node: LogicExpr, z3_vars: dict[str, z3.ExprRef]
    ) -> z3.ExprRef:
        cond = self._eval_z3(node.cond or LogicExpr(kind="literal_int"), z3_vars)
        t_br = self._eval_z3(
            node.then_branch or LogicExpr(kind="literal_real"), z3_vars
        )
        e_br = self._eval_z3(
            node.else_branch or LogicExpr(kind="literal_real"), z3_vars
        )
        if z3.is_real(t_br) and z3.is_int(e_br):
            e_br = z3.ToReal(e_br)
        elif z3.is_int(t_br) and z3.is_real(e_br):
            t_br = z3.ToReal(t_br)
        return z3.If(cond, t_br, e_br)

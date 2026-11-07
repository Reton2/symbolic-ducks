from typing import Any

from z3 import (
    And,
    Bool,
    BoolVal,
    Int,
    IntVal,
    Not,
    Or,
    Real,
    RealVal,
    Solver,
    String,
    StringVal,
    is_int_value,
    is_rational_value,
    is_true,
    sat,
)

from app.schemas.schemas import (
    ComparisonNode,
    LogicalGroupNode,
    PolicyDocumentBundle,
    PolicyItem,
)


class Z3PolicyProver:
    def __init__(
        self,
        bundle: PolicyDocumentBundle,
        param_overrides: dict[str, Any] | None = None,
    ):
        self.bundle = bundle
        self.params = {k: v.value for k, v in bundle.parameters.items()}
        if param_overrides:
            self.params.update(param_overrides)

        self.vars = self._create_symbolic_vars("")
        self.vars_t1 = self._create_symbolic_vars("t1_")
        self.vars_t2 = self._create_symbolic_vars("t2_")

    def _create_symbolic_vars(self, prefix: str) -> dict[str, Any]:
        v = {}
        for field, ftype in self.bundle.fields.items():
            name = f"{prefix}{field}"
            if ftype == "real":
                v[field] = Real(name)
            elif ftype == "int":
                v[field] = Int(name)
            elif ftype == "string":
                v[field] = String(name)
            elif ftype == "bool":
                v[field] = Bool(name)
        return v

    def _build_axioms(self, v_map: dict[str, Any]) -> list[Any]:
        constraints = []
        for ax in self.bundle.axioms:
            if ax.field in v_map:
                var = v_map[ax.field]
                if ax.min_val is not None:
                    constraints.append(
                        var
                        >= (
                            RealVal(ax.min_val)
                            if self.bundle.fields[ax.field] == "real"
                            else IntVal(int(ax.min_val))
                        )
                    )
                if ax.max_val is not None:
                    constraints.append(
                        var
                        <= (
                            RealVal(ax.max_val)
                            if self.bundle.fields[ax.field] == "real"
                            else IntVal(int(ax.max_val))
                        )
                    )
                if ax.window_accumulates_field and ax.window_accumulates_field in v_map:
                    constraints.append(var >= v_map[ax.window_accumulates_field])
        return constraints

    def _resolve_rhs(self, node: ComparisonNode, v_map: dict[str, Any]):
        if node.right_field:
            return v_map[node.right_field] * RealVal(node.right_multiplier)
        raw_val = (
            self.params.get(node.param_ref, node.literal_value)
            if node.param_ref
            else node.literal_value
        )
        ftype = self.bundle.fields[node.left_field]
        if isinstance(raw_val, list):
            return [StringVal(str(x)) for x in raw_val]
        if ftype == "real":
            return RealVal(float(raw_val))
        if ftype == "int":
            return IntVal(int(raw_val))
        if ftype == "bool":
            return BoolVal(bool(raw_val))
        return StringVal(str(raw_val))

    def compile_node(self, node: Any, v_map: dict[str, Any] | None = None):
        v_map = v_map or self.vars
        if (
            isinstance(node, LogicalGroupNode)
            or getattr(node, "node_type", None) == "LOGICAL"
        ):
            children = [self.compile_node(c, v_map) for c in node.children]
            if node.logic_op == "AND":
                return And(*children)
            if node.logic_op == "OR":
                return Or(*children)
            if node.logic_op == "NOT":
                return Not(children[0])

        lhs = v_map[node.left_field]
        rhs = self._resolve_rhs(node, v_map)
        op = node.operator
        if op == "==":
            return lhs == rhs
        if op == "!=":
            return lhs != rhs
        if op == ">":
            return lhs > rhs
        if op == ">=":
            return lhs >= rhs
        if op == "<":
            return lhs < rhs
        if op == "<=":
            return lhs <= rhs
        if op == "IN" and isinstance(rhs, list):
            return Or(*[lhs == item for item in rhs])
        return lhs == rhs

    def _extract_model_dict(self, model, v_map: dict[str, Any]) -> dict[str, Any]:
        out = {}
        for field, ftype in self.bundle.fields.items():
            val = model[v_map[field]]
            if val is None:
                out[field] = "UNCONSTRAINED"
            elif is_rational_value(val):
                out[field] = round(
                    float(val.numerator_as_long()) / float(val.denominator_as_long()), 2
                )
            elif is_int_value(val):
                out[field] = int(val.as_long())
            elif ftype == "bool":
                out[field] = bool(is_true(val))
            else:
                out[field] = str(val).strip('"')
        return out

    def run_full_verification_suite(self) -> dict[str, Any]:
        issues = []
        rule_proofs = []
        active_policies = [p for p in self.bundle.policies if p.enabled]

        for k, val in self.params.items():
            spec = self.bundle.parameters.get(k)
            if spec and isinstance(val, (int, float)):
                if spec.min_bound is not None and val < spec.min_bound:
                    issues.append(
                        {
                            "type": "AXIOM_VIOLATION",
                            "policy_id": spec.policy_id,
                            "detail": f"Parameter `{k}` ({val}) < min bound ({spec.min_bound}).",
                        }
                    )
                if spec.max_bound is not None and val > spec.max_bound:
                    issues.append(
                        {
                            "type": "AXIOM_VIOLATION",
                            "policy_id": spec.policy_id,
                            "detail": f"Parameter `{k}` ({val}) > max bound ({spec.max_bound}).",
                        }
                    )

        compiled_policies = [
            (p, self.compile_node(p.root_node, self.vars)) for p in active_policies
        ]
        base_axioms = self._build_axioms(self.vars)

        for idx, (pol, expr) in enumerate(compiled_policies):
            s = Solver()
            s.add(*base_axioms)
            s.add(expr)
            is_sat = s.check() == sat
            if not is_sat:
                issues.append(
                    {
                        "type": "UNSATISFIABLE_POLICY",
                        "policy_id": pol.policy_id,
                        "detail": f"Policy `{pol.policy_id}` ({pol.name}) is mathematically UNSATISFIABLE (Dead Logic).",
                    }
                )

            for jdx, (other_pol, other_expr) in enumerate(compiled_policies):
                if idx >= jdx:
                    continue
                if pol.action != other_pol.action:
                    sc = Solver()
                    sc.add(*base_axioms)
                    sc.add(And(expr, other_expr))
                    if sc.check() == sat:
                        witness = self._extract_model_dict(sc.model(), self.vars)
                        issues.append(
                            {
                                "type": "CONTRADICTION",
                                "policy_id": f"{pol.policy_id} vs {other_pol.policy_id}",
                                "detail": f"Conflicting actions ({pol.action} vs {other_pol.action}) fire simultaneously.",
                                "witness": witness,
                            }
                        )
                else:
                    ss = Solver()
                    ss.add(*base_axioms)
                    ss.add(And(other_expr, Not(expr)))
                    if ss.check() != sat:
                        issues.append(
                            {
                                "type": "SHADOWED_POLICY",
                                "policy_id": other_pol.policy_id,
                                "detail": f"Policy `{other_pol.policy_id}` is 100% shadowed/subsumed by `{pol.policy_id}`.",
                            }
                        )

            smurf_res = self._check_smurfing(pol)
            if smurf_res["vulnerable"] and pol.action == "INTERCEPT":
                issues.append(
                    {
                        "type": "SMURFING_LOOPHOLE",
                        "policy_id": pol.policy_id,
                        "detail": smurf_res["detail"],
                        "witness": smurf_res["witness"],
                    }
                )

            rule_proofs.append(
                {
                    "policy_id": pol.policy_id,
                    "name": pol.name,
                    "satisfiable": is_sat,
                    "smurfing_immune": not smurf_res["vulnerable"],
                }
            )

        return {
            "overall_status": "VERIFIED" if not issues else "FAILED_PROOF",
            "issue_count": len(issues),
            "issues": issues,
            "rule_proofs": rule_proofs,
            "red_team_adversarial_sample": self.synthesize_red_team_bypass(),
        }

    def _check_smurfing(self, pol: PolicyItem) -> dict[str, Any]:
        pf = self.bundle.primary_value_field
        wf = self.bundle.window_value_field
        s = Solver()
        s.add(*self._build_axioms(self.vars))
        s.add(*self._build_axioms(self.vars_t1))
        s.add(*self._build_axioms(self.vars_t2))

        e_single = self.compile_node(pol.root_node, self.vars)
        e_t1 = self.compile_node(pol.root_node, self.vars_t1)
        e_t2 = self.compile_node(pol.root_node, self.vars_t2)

        s.add(self.vars[pf] == self.vars_t1[pf] + self.vars_t2[pf])
        s.add(self.vars[wf] == self.vars[pf])
        s.add(self.vars_t1[wf] == self.vars_t1[pf])
        s.add(self.vars_t2[wf] == self.vars_t1[pf] + self.vars_t2[pf])

        for f in self.bundle.fields:
            if f not in (pf, wf):
                s.add(self.vars_t1[f] == self.vars[f])
                s.add(self.vars_t2[f] == self.vars[f])

        s.add(e_single)
        s.add(Not(e_t1))
        s.add(Not(e_t2))

        if s.check() == sat:
            m = s.model()
            w_s = self._extract_model_dict(m, self.vars)[pf]
            w_1 = self._extract_model_dict(m, self.vars_t1)[pf]
            w_2 = self._extract_model_dict(m, self.vars_t2)[pf]
            return {
                "vulnerable": True,
                "detail": f"Single transaction ({w_s}) is blocked, but splitting into ({w_1} + {w_2}) evades `{pol.policy_id}`.",
                "witness": {
                    "blocked_single": w_s,
                    "bypass_split_1": w_1,
                    "bypass_split_2": w_2,
                },
            }
        return {"vulnerable": False}

    def synthesize_red_team_bypass(self) -> dict[str, Any]:
        """Synthesizes an adversarial boundary event that evades all INTERCEPT policies while maximizing risk/value."""
        s = Solver()
        s.add(*self._build_axioms(self.vars))
        for p in self.bundle.policies:
            if p.enabled and p.action == "INTERCEPT":
                s.add(Not(self.compile_node(p.root_node, self.vars)))

        pf = self.bundle.primary_value_field
        # Push primary value near the single-order threshold to simulate an intelligent boundary attacker
        first_num = next(
            (
                v
                for v in self.params.values()
                if isinstance(v, (int, float)) and v > 100
            ),
            50000.0,
        )
        s.add(self.vars[pf] >= RealVal(float(first_num) * 0.96))

        if s.check() == sat:
            model_dict = self._extract_model_dict(s.model(), self.vars)
            model_dict["event_id"] = "ev_z3_redteam"
            model_dict[self.bundle.entity_key] = "REDTEAM_ACTOR"
            model_dict["_is_anomalous_attack"] = True
            return {"status": "BYPASS_SYNTHESIZED", "payload": model_dict}
        return {"status": "FULLY_CONSTRAINED", "payload": {}}

    def infer_input_states(self, partial_state: dict[str, Any]) -> dict[str, Any]:
        """
        Given partial user-supplied field constraints, uses Z3 to infer:
        1) A concrete state completion that triggers INTERCEPT (and which policy triggers it).
        2) A concrete high-value state completion that guarantees PASS across all policies.
        3) Policy-by-policy reachability under the given partial state.
        """
        fixed_constraints = []
        for field, val in partial_state.items():
            if field in self.vars and val is not None and val != "":
                ftype = self.bundle.fields[field]
                if ftype == "real":
                    fixed_constraints.append(self.vars[field] == RealVal(float(val)))
                elif ftype == "int":
                    fixed_constraints.append(
                        self.vars[field] == IntVal(int(float(val)))
                    )
                elif ftype == "bool":
                    b_val = (
                        val if isinstance(val, bool) else (str(val).lower() == "true")
                    )
                    fixed_constraints.append(self.vars[field] == BoolVal(b_val))
                else:
                    fixed_constraints.append(self.vars[field] == StringVal(str(val)))

        active_intercepts = [
            (p, self.compile_node(p.root_node, self.vars))
            for p in self.bundle.policies
            if p.enabled and p.action == "INTERCEPT"
        ]

        # 1. Infer state that triggers INTERCEPT
        s_int = Solver()
        s_int.add(*self._build_axioms(self.vars))
        s_int.add(*fixed_constraints)
        if active_intercepts:
            s_int.add(Or(*[expr for _, expr in active_intercepts]))
        intercept_state = (
            self._extract_model_dict(s_int.model(), self.vars)
            if (active_intercepts and s_int.check() == sat)
            else None
        )

        # 2. Infer state that guarantees PASS
        s_pass = Solver()
        s_pass.add(*self._build_axioms(self.vars))
        s_pass.add(*fixed_constraints)
        for _, expr in active_intercepts:
            s_pass.add(Not(expr))
        pass_state = (
            self._extract_model_dict(s_pass.model(), self.vars)
            if s_pass.check() == sat
            else None
        )

        # 3. Per-policy reachability under partial state
        policy_reachability = []
        for p, expr in active_intercepts:
            sp = Solver()
            sp.add(*self._build_axioms(self.vars))
            sp.add(*fixed_constraints)
            sp.add(expr)
            can_fire = sp.check() == sat
            policy_reachability.append(
                {
                    "policy_id": p.policy_id,
                    "name": p.name,
                    "can_trigger_under_partial_state": can_fire,
                    "witness_if_triggered": self._extract_model_dict(
                        sp.model(), self.vars
                    )
                    if can_fire
                    else None,
                }
            )

        return {
            "partial_constraints_applied": partial_state,
            "inferred_intercept_witness": intercept_state,
            "inferred_safe_pass_witness": pass_state,
            "policy_reachability": policy_reachability,
        }

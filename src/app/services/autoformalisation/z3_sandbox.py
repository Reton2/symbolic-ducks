from __future__ import annotations

import ast
import json
import logging
from collections.abc import Sequence
from typing import Any

import z3
from z3 import (
    And,
    Bool,
    BoolRef,
    BoolVal,
    Implies,
    Int,
    IntVal,
    Not,
    Or,
    Real,
    RealVal,
    ToInt,
    ToReal,
    Xor,
    is_bool,
    is_const,
    is_expr,
    is_int,
    is_real,
)

from app.services.autoformalisation.models import (
    CausalLink,
    EquationSynthesisResponse,
    ResolvedConcept,
)
from app.services.smt.smt_helpers import (
    TargetSortMode,
    destruct_z3_expr,
    extract_z3_dependencies,
    z3_if,
)

from .err import Z3SandboxExecutionError

logger = logging.getLogger(__name__)


class Z3SandboxVarStore(dict[str, Any]):
    """Symbolic Z3 variable store that auto-mints Real(key) on missing lookups."""

    def __missing__(self, key: str) -> Any:
        zvar = Real(str(key))
        self[str(key)] = zvar
        return zvar


class Z3CodeSandbox:
    """AST-validated Z3 constraint sandbox executing `W_hat` constraint lists."""

    _ALLOWED_CALL_NAMES = frozenset(
        {
            "And",
            "Or",
            "Not",
            "If",
            "Xor",
            "Implies",
            "Real",
            "Int",
            "Bool",
            "RealVal",
            "IntVal",
            "BoolVal",
            "ToReal",
            "ToInt",
        }
    )
    _ALLOWED_METHODS = frozenset({"append", "extend"})

    @classmethod
    def _validate_ast(cls, code_str: str) -> None:
        tree = ast.parse(code_str, mode="exec")
        for node in ast.walk(tree):
            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.Lambda,
                    ast.Delete,
                    ast.Global,
                    ast.Nonlocal,
                    ast.With,
                    ast.AsyncWith,
                    ast.Try,
                    ast.Raise,
                    ast.Subscript,
                    ast.While,
                    ast.For,
                    ast.AsyncFor,
                ),
            ):
                raise ValueError(f"Disallowed syntax in sandbox: {type(node).__name__}")
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise ValueError(f"Disallowed identifier in sandbox: {node.id}")
            if isinstance(node, ast.Assign) and (
                len(node.targets) != 1
                or not isinstance(node.targets[0], ast.Name)
                or node.targets[0].id != "W_hat"
            ):
                raise ValueError("Only assignment to 'W_hat' is permitted in sandbox")
            if isinstance(node, ast.Attribute) and (
                node.attr not in cls._ALLOWED_METHODS
                or not (isinstance(node.value, ast.Name) and node.value.id == "W_hat")
            ):
                raise ValueError(f"Disallowed attribute access: {node.attr}")
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id not in cls._ALLOWED_CALL_NAMES:
                        raise ValueError(f"Disallowed function call: {node.func.id}")
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr not in cls._ALLOWED_METHODS:
                        raise ValueError(f"Disallowed method call: {node.func.attr}")
                else:
                    raise ValueError("Disallowed callable expression in sandbox")

    @classmethod
    def execute_constraints(
        cls,
        scope: Z3SandboxVarStore,
        llm_code_response: str,
    ) -> tuple[list[BoolRef] | None, str | None]:
        try:
            cls._validate_ast(llm_code_response)
            exec(llm_code_response, {"__builtins__": {}}, scope)
            w_hat_rules = scope.get("W_hat", [])
            if not isinstance(w_hat_rules, list) or len(w_hat_rules) == 0:
                return None, "Empty or missing W_hat list"
            for item in w_hat_rules:
                if not isinstance(item, BoolRef):
                    return None, f"Invalid Z3 BoolRef element: {type(item)}"
            return w_hat_rules, None
        except Exception as exc:
            return None, f"{type(exc).__name__}: {str(exc)}"


class Z3SynthesisSandbox:
    """Isolated Z3 execution sandbox for `W_hat` Z3 constraint synthesis."""

    def __init__(
        self,
        concepts: dict[str, ResolvedConcept],
        links: list[CausalLink],
    ) -> None:
        self.concepts = concepts
        self.links = links
        self.v = Z3SandboxVarStore()
        self.parameters: dict[str, dict[str, Any]] = {}
        self.equations: dict[str, dict[str, Any]] = {}
        self._init_concept_variables()

    def _init_concept_variables(self) -> None:
        for cid, c in self.concepts.items():
            if c.sort == "real":
                zvar: Any = Real(cid)
            elif c.sort == "int":
                zvar = Int(cid)
            else:
                zvar = Bool(cid)
            self.v[cid] = zvar

    def _get_target_sort(self, target_var: str) -> TargetSortMode:
        if target_var in self.concepts:
            return self.concepts[target_var].sort
        if target_var in self.v and is_expr(self.v[target_var]):
            zvar = self.v[target_var]
            if is_int(zvar):
                return "int"
            if is_real(zvar):
                return "real"
            if is_bool(zvar):
                return "bool"
        return "auto"

    def _infer_parent_for_param(
        self, param_id: str, sibling_deps: Sequence[str]
    ) -> ResolvedConcept | None:
        for dep in sibling_deps:
            if dep in self.concepts and dep in param_id:
                return self.concepts[dep]
        for cid, c in self.concepts.items():
            if cid in param_id:
                return c
        for dep in sibling_deps:
            if dep in self.concepts and not self.concepts[dep].ordinal_levels:
                return self.concepts[dep]
        return None

    def _ensure_implicit_parameters(
        self, deps: Sequence[str], sids: Sequence[int]
    ) -> None:
        for dep in deps:
            if dep not in self.concepts and dep not in self.parameters:
                parent_c = self._infer_parent_for_param(dep, deps)
                if parent_c is not None and not parent_c.ordinal_levels:
                    inferred_sort = "int" if parent_c.sort == "int" else "real"
                    min_b = float(parent_c.min_bound)
                    max_b = float(parent_c.max_bound)
                else:
                    zvar = self.v.get(dep)
                    inferred_sort = (
                        "int" if (is_expr(zvar) and is_int(zvar)) else "real"
                    )
                    min_b = 0.0
                    max_b = 100.0

                is_low_bad = any(
                    w in dep
                    for w in (
                        "depth",
                        "correlation",
                        "alpha",
                        "return",
                        "momentum",
                        "capacity",
                        "feasibility",
                        "quality",
                    )
                )
                ratio = 0.25 if is_low_bad else 0.70
                def_val = round((max_b - min_b) * ratio + min_b, 2)
                if inferred_sort == "int":
                    def_val = float(int(round(def_val)))

                self.parameters[dep] = {
                    "var_id": dep,
                    "human_name": dep.replace("_", " ").title(),
                    "sort": inferred_sort,
                    "min_bound": min_b,
                    "max_bound": max_b,
                    "default_value": def_val,
                    "source_sentence_ids": [int(s) for s in sids],
                }

    def register_equation(
        self,
        target_var: str,
        smt_expression: Any,
        natural_language_logic: str = "",
        source_sentence_ids: Sequence[int] = (),
        dependencies: Sequence[str] = (),
        equation_id: str = "",
    ) -> dict[str, Any]:
        """Registers a derived variable's Z3 symbolic expression and destructs its AST."""
        target_sort = self._get_target_sort(target_var)
        expr_str = destruct_z3_expr(smt_expression, target_sort=target_sort)
        ast_deps = extract_z3_dependencies(smt_expression)
        if not ast_deps:
            ast_deps = extract_z3_dependencies(expr_str)

        merged_deps: list[str] = []
        for d in [*dependencies, *ast_deps]:
            if d != target_var and d not in merged_deps:
                merged_deps.append(d)

        sids = [int(s) for s in source_sentence_ids]
        if not sids and target_var in self.concepts:
            sids = sorted(self.concepts[target_var].sentence_ids)

        self._ensure_implicit_parameters(merged_deps, sids)
        entry = {
            "equation_id": equation_id or f"eq_{target_var}",
            "target_var": target_var,
            "dependencies": merged_deps,
            "smt_expression": expr_str,
            "natural_language_logic": natural_language_logic
            or f"Synthesized Z3 rule for {target_var}",
            "source_sentence_ids": sids,
        }
        self.equations[target_var] = entry
        return entry

    def _normalize_param_dict(self, raw_params: Any) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = dict(self.parameters)
        items: list[tuple[str, Any]] = []
        if isinstance(raw_params, dict):
            items = [(str(k), val) for k, val in raw_params.items()]
        elif isinstance(raw_params, list):
            for item in raw_params:
                if isinstance(item, dict):
                    pid = str(
                        item.get("var_id") or item.get("id") or f"param_{len(items)}"
                    )
                    items.append((pid, item))

        for pid, spec in items:
            if isinstance(spec, dict):
                var_id = str(spec.get("var_id") or pid)
                out[var_id] = {
                    "var_id": var_id,
                    "human_name": str(
                        spec.get("human_name") or spec.get("name") or var_id
                    ),
                    "sort": str(spec.get("sort") or "real"),
                    "min_bound": spec.get("min_bound", 0.0),
                    "max_bound": spec.get("max_bound", 100.0),
                    "default_value": spec.get("default_value", 10.0),
                    "source_sentence_ids": spec.get("source_sentence_ids", []),
                }
        return out

    def _normalize_equations_dict(
        self, raw_equations: Any
    ) -> dict[str, dict[str, Any]]:
        items: list[tuple[str, Any]] = []
        if isinstance(raw_equations, dict):
            items = [(str(k), val) for k, val in raw_equations.items()]
        elif isinstance(raw_equations, list):
            for item in raw_equations:
                if isinstance(item, dict):
                    tid = str(
                        item.get("target_var")
                        or item.get("target_id")
                        or f"eq_{len(items)}"
                    )
                    items.append((tid, item))

        for tid, spec in items:
            if isinstance(spec, dict):
                target_var = str(spec.get("target_var") or spec.get("target_id") or tid)
                raw_expr = spec.get("smt_expression", spec.get("expr", ""))
                self.register_equation(
                    target_var=target_var,
                    smt_expression=raw_expr,
                    natural_language_logic=str(
                        spec.get("natural_language_logic") or ""
                    ),
                    source_sentence_ids=spec.get("source_sentence_ids") or (),
                    dependencies=spec.get("dependencies") or (),
                    equation_id=str(spec.get("equation_id") or f"eq_{target_var}"),
                )
            else:
                self.register_equation(target_var=tid, smt_expression=spec)
        return dict(self.equations)

    def _harvest_w_hat_constraints(self, w_hat_rules: Sequence[Any]) -> None:
        link_logic_by_target: dict[str, list[str]] = {}
        link_sids_by_target: dict[str, set[int]] = {}
        for lnk in self.links:
            if lnk.logic_summary:
                link_logic_by_target.setdefault(lnk.target_id, []).append(
                    lnk.logic_summary
                )
            link_sids_by_target.setdefault(lnk.target_id, set()).add(lnk.sentence_id)

        for assertion in w_hat_rules:
            if not is_expr(assertion) or assertion.decl().kind() not in (
                z3.Z3_OP_EQ,
                z3.Z3_OP_IFF,
            ):
                continue
            lhs, rhs = assertion.arg(0), assertion.arg(1)
            if is_const(lhs) and lhs.decl().kind() == z3.Z3_OP_UNINTERPRETED:
                target_var, expr = str(lhs), rhs
            elif is_const(rhs) and rhs.decl().kind() == z3.Z3_OP_UNINTERPRETED:
                target_var, expr = str(rhs), lhs
            else:
                continue

            nl_logic = "; ".join(link_logic_by_target.get(target_var, ()))
            sids = sorted(link_sids_by_target.get(target_var, set()))
            self.register_equation(
                target_var=target_var,
                smt_expression=expr,
                natural_language_logic=nl_logic,
                source_sentence_ids=sids,
            )

    def destruct_z3_model(
        self,
        parameters: Any = (),
        equations: Any = (),
    ) -> dict[str, Any]:
        """Destructs constructed Z3 parameters and AST equations into the JSON contract."""
        if parameters:
            self.parameters = self._normalize_param_dict(parameters)
        if equations:
            self._normalize_equations_dict(equations)
        return {
            "parameters": dict(self.parameters),
            "equations": dict(self.equations),
        }

    def _build_sandbox_scope(self) -> Z3SandboxVarStore:
        scope = Z3SandboxVarStore(
            {
                "And": And,
                "Or": Or,
                "Not": Not,
                "If": z3_if,
                "Xor": Xor,
                "Implies": Implies,
                "Real": Real,
                "Int": Int,
                "Bool": Bool,
                "RealVal": RealVal,
                "IntVal": IntVal,
                "BoolVal": BoolVal,
                "ToReal": ToReal,
                "ToInt": ToInt,
                "True": True,
                "False": False,
                "W_hat": [],
            }
        )
        for var_name, z3_var in self.v.items():
            scope[var_name] = z3_var
        return scope

    def execute(self, code_str: str) -> EquationSynthesisResponse:
        """Executes `W_hat` Z3 constraints in `Z3CodeSandbox` and returns destructed JSON schema."""
        if not code_str:
            return EquationSynthesisResponse()

        # Support direct JSON payloads seamlessly if returned by mocks or fallback models
        if code_str.startswith("{"):
            try:
                parsed_json = json.loads(code_str)
                if isinstance(parsed_json, dict) and (
                    "equations" in parsed_json or "parameters" in parsed_json
                ):
                    destructed = self.destruct_z3_model(
                        parsed_json.get("parameters", ()),
                        parsed_json.get("equations", ()),
                    )
                    return EquationSynthesisResponse.model_validate(destructed)
            except Exception:
                pass

        scope = self._build_sandbox_scope()
        w_hat_rules, err_msg = Z3CodeSandbox.execute_constraints(scope, code_str)
        if err_msg is not None or w_hat_rules is None:
            logger.error("Z3 Python sandbox execution failed: %s", err_msg)
            raise Z3SandboxExecutionError(
                f"Failed to execute synthesized Z3 constraints in sandbox: {err_msg}"
            )

        for k, val in scope.items():
            if k not in self.v and is_expr(val):
                self.v[k] = val

        self._harvest_w_hat_constraints(w_hat_rules)
        destructed_payload = self.destruct_z3_model()
        return EquationSynthesisResponse.model_validate(destructed_payload)

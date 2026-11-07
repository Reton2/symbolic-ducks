from __future__ import annotations

import logging
import re
from typing import Any, Literal

import z3
from z3 import (
    And,
    BoolVal,
    If,
    IntVal,
    Not,
    Or,
    RealVal,
    ToInt,
    ToReal,
    is_bool,
    is_const,
    is_expr,
    is_false,
    is_int,
    is_int_value,
    is_rational_value,
    is_real,
    is_true,
)

logger = logging.getLogger("app.control.smt_helpers")

TargetSortMode = Literal["real", "int", "bool", "auto"]


class SMTExpressionSyntaxError(Exception):
    """Raised when an SMT symbolic formula cannot be evaluated or parsed."""


def _to_z3_val(val: Any) -> Any:
    """Coerces Python scalar literals into Z3 symbolic values when needed."""
    if is_expr(val):
        return val
    if isinstance(val, bool):
        return BoolVal(val)
    if isinstance(val, int):
        return IntVal(val)
    if isinstance(val, float):
        return RealVal(val)
    return val


def _align_numeric_pair(a: Any, b: Any) -> tuple[Any, Any]:
    """Ensures two symbolic or scalar numeric values share a compatible Z3 sort."""
    za = _to_z3_val(a)
    zb = _to_z3_val(b)
    if is_expr(za) and is_expr(zb):
        if is_real(za) and is_int(zb):
            return za, ToReal(zb)
        if is_int(za) and is_real(zb):
            return ToReal(za), zb
    return za, zb


def z3_if(cond: Any, t_val: Any, f_val: Any) -> Any:
    """Sort-aligned wrapper around `z3.If` that coerces mixed int/real branches."""
    lhs, rhs = _align_numeric_pair(t_val, f_val)
    return If(_to_z3_val(cond), lhs, rhs)


def z3_min(*args: Any) -> Any:
    """Symbolic minimum conditional across one or more Z3 expressions."""
    if not args:
        raise ValueError("z3_min requires at least one argument")
    if len(args) == 1:
        return _to_z3_val(args[0])
    res = _to_z3_val(args[0])
    for item in args[1:]:
        lhs, rhs = _align_numeric_pair(res, item)
        res = If(lhs <= rhs, lhs, rhs)
    return res


def z3_max(*args: Any) -> Any:
    """Symbolic maximum conditional across one or more Z3 expressions."""
    if not args:
        raise ValueError("z3_max requires at least one argument")
    if len(args) == 1:
        return _to_z3_val(args[0])
    res = _to_z3_val(args[0])
    for item in args[1:]:
        lhs, rhs = _align_numeric_pair(res, item)
        res = If(lhs >= rhs, lhs, rhs)
    return res


def num_not(x: Any, max_val: float = 100.0) -> Any:
    """Continuous numerical complement (max_val - x) on a [0.0, max_val] intensity scale."""
    zx = _to_z3_val(x)
    if is_expr(zx):
        rx = ToReal(zx) if is_int(zx) else zx
        return RealVal(float(max_val)) - rx
    return float(max_val) - float(x)


def ord_not(x: Any, max_val: int = 4) -> Any:
    """Discrete ordinal complement (max_val - x) for integer tier rankings 0..max_val."""
    zx = _to_z3_val(x)
    if is_expr(zx):
        ix = ToInt(zx) if is_real(zx) else zx
        return IntVal(int(max_val)) - ix
    return int(max_val) - int(x)


def native_min(*args: float | int) -> float:
    """Native numeric minimum with safe float casting for fast-path runtime."""
    if not args:
        raise ValueError("native_min requires at least one argument")
    if len(args) == 1:
        return float(args[0])
    return min(float(x) for x in args)


def native_max(*args: float | int) -> float:
    """Native numeric maximum with safe float casting for fast-path runtime."""
    if not args:
        raise ValueError("native_max requires at least one argument")
    if len(args) == 1:
        return float(args[0])
    return max(float(x) for x in args)


def native_num_not(x: float | int, max_val: float = 100.0) -> float:
    """Native numeric complement (max_val - x) for fast-path runtime."""
    return float(max_val) - float(x)


def native_ord_not(x: float | int, max_val: int = 4) -> int:
    """Native discrete ordinal complement (max_val - x) for fast-path runtime."""
    return int(max_val) - int(x)


def extract_z3_dependencies(expr: Any) -> list[str]:
    """Extracts all referenced variable identifiers from a Z3 AST or expression string."""
    if isinstance(expr, str):
        found = re.findall(r"v\[\s*['\"]([a-zA-Z0-9_]+)['\"]\s*\]", expr)
        seen: list[str] = []
        for item in found:
            if item not in seen:
                seen.append(item)
        return seen

    if not is_expr(expr):
        return []

    visited: set[int] = set()
    deps: list[str] = []

    def _walk(node: z3.ExprRef) -> None:
        nid = node.get_id()
        if nid in visited:
            return
        visited.add(nid)
        if (
            is_const(node)
            and node.decl().kind() == z3.Z3_OP_UNINTERPRETED
            and not is_int_value(node)
            and not is_rational_value(node)
            and not is_true(node)
            and not is_false(node)
        ):
            name = str(node)
            if name not in deps:
                deps.append(name)
            return
        for child in node.children():
            _walk(child)

    _walk(expr)
    return deps


def _destruct_scalar(val: Any, target_sort: TargetSortMode) -> str:
    if isinstance(val, bool):
        if target_sort == "int":
            return "1" if val else "0"
        if target_sort == "real":
            return "100.0" if val else "0.0"
        return "True" if val else "False"
    if isinstance(val, int):
        if target_sort == "real":
            return f"{float(val)}"
        if target_sort == "bool":
            return "True" if val > 0 else "False"
        return str(val)
    if isinstance(val, float):
        if target_sort == "int":
            return str(int(round(val)))
        if target_sort == "bool":
            return "True" if val > 0.0 else "False"
        return str(round(val, 6))
    return str(val)


def _destruct_const_node(expr: z3.ExprRef, target_sort: TargetSortMode) -> str | None:
    if is_true(expr) or is_false(expr):
        return _destruct_scalar(is_true(expr), target_sort)
    if is_int_value(expr):
        return _destruct_scalar(int(expr.as_long()), target_sort)
    if is_rational_value(expr):
        rval = round(
            float(expr.numerator_as_long()) / float(expr.denominator_as_long()), 6
        )
        return _destruct_scalar(rval, target_sort)
    if is_const(expr) and expr.decl().kind() == z3.Z3_OP_UNINTERPRETED:
        base = f"v['{expr}']"
        if target_sort == "int" and is_real(expr):
            return f"ToInt({base})"
        if target_sort == "real" and is_int(expr):
            return f"ToReal({base})"
        return base
    return None


def _destruct_ite_node(expr: z3.ExprRef, target_sort: TargetSortMode) -> str:
    cond, t_br, f_br = expr.arg(0), expr.arg(1), expr.arg(2)
    return (
        f"If({destruct_z3_expr(cond, 'bool')}, "
        f"{destruct_z3_expr(t_br, target_sort)}, "
        f"{destruct_z3_expr(f_br, target_sort)})"
    )


_BINARY_CMP_OPS: dict[int, str] = {
    z3.Z3_OP_LE: "<=",
    z3.Z3_OP_LT: "<",
    z3.Z3_OP_GE: ">=",
    z3.Z3_OP_GT: ">",
    z3.Z3_OP_EQ: "==",
    z3.Z3_OP_IFF: "==",
    z3.Z3_OP_DISTINCT: "!=",
}

_NARY_ARITH_OPS: dict[int, str] = {
    z3.Z3_OP_ADD: " + ",
    z3.Z3_OP_SUB: " - ",
    z3.Z3_OP_MUL: " * ",
}


def _destruct_compound_node(expr: z3.ExprRef, target_sort: TargetSortMode) -> str:
    kind = expr.decl().kind()
    if kind == z3.Z3_OP_ITE:
        return _destruct_ite_node(expr, target_sort)
    if kind == z3.Z3_OP_AND:
        return f"And({', '.join(destruct_z3_expr(c, 'bool') for c in expr.children())})"
    if kind == z3.Z3_OP_OR:
        return f"Or({', '.join(destruct_z3_expr(c, 'bool') for c in expr.children())})"
    if kind == z3.Z3_OP_NOT:
        return f"Not({destruct_z3_expr(expr.arg(0), 'bool')})"
    if kind == z3.Z3_OP_IMPLIES:
        return f"Or(Not({destruct_z3_expr(expr.arg(0), 'bool')}), {destruct_z3_expr(expr.arg(1), 'bool')})"
    if kind in _BINARY_CMP_OPS:
        op_str = _BINARY_CMP_OPS[kind]
        return f"({destruct_z3_expr(expr.arg(0))} {op_str} {destruct_z3_expr(expr.arg(1))})"
    if kind in _NARY_ARITH_OPS:
        sep = _NARY_ARITH_OPS[kind]
        inner = f"({sep.join(destruct_z3_expr(c) for c in expr.children())})"
        return f"ToInt({inner})" if target_sort == "int" and is_real(expr) else inner
    if kind in (z3.Z3_OP_DIV, z3.Z3_OP_IDIV):
        inner = f"({destruct_z3_expr(expr.arg(0))} / {destruct_z3_expr(expr.arg(1))})"
        return f"ToInt({inner})" if target_sort == "int" else inner
    if kind == z3.Z3_OP_UMINUS:
        return f"(-{destruct_z3_expr(expr.arg(0), target_sort)})"
    if kind == z3.Z3_OP_TO_REAL:
        inner_str = destruct_z3_expr(expr.arg(0), "auto")
        return inner_str if target_sort == "int" else f"ToReal({inner_str})"
    if kind == z3.Z3_OP_TO_INT:
        return f"ToInt({destruct_z3_expr(expr.arg(0), 'auto')})"
    return str(expr)


def destruct_z3_expr(expr: Any, target_sort: TargetSortMode = "auto") -> str:
    """Decompiles a constructed Z3 ExprRef AST into a canonical `v['var_id']` expression string."""
    if isinstance(expr, str):
        return expr.strip()
    if not is_expr(expr):
        return _destruct_scalar(expr, target_sort)

    if is_bool(expr) and target_sort == "int" and not (is_true(expr) or is_false(expr)):
        return f"If({destruct_z3_expr(expr, 'bool')}, 1, 0)"
    if (
        is_bool(expr)
        and target_sort == "real"
        and not (is_true(expr) or is_false(expr))
    ):
        return f"If({destruct_z3_expr(expr, 'bool')}, 100.0, 0.0)"

    const_str = _destruct_const_node(expr, target_sort)
    if const_str is not None:
        return const_str
    return _destruct_compound_node(expr, target_sort)


def evaluate_z3_symbolic_expression(expr_str: str, z3_vars: dict[str, Any]) -> Any:
    """Safely evaluates a pure Z3 symbolic expression string within an isolated environment.

    Supported primitives:
      - Variables dictionary: v['var_id']
      - Connectives: And, Or, Not, If
      - Bounding & polarity functions: z3_min, z3_max, num_not, ord_not
      - Sort constructors: RealVal, IntVal, BoolVal, ToReal, ToInt
      - Literals: True, False
    """
    safe_env: dict[str, Any] = {
        "v": z3_vars,
        "And": And,
        "Or": Or,
        "Not": Not,
        "If": z3_if,
        "z3_min": z3_min,
        "z3_max": z3_max,
        "num_not": num_not,
        "ord_not": ord_not,
        "RealVal": RealVal,
        "IntVal": IntVal,
        "BoolVal": BoolVal,
        "ToReal": ToReal,
        "ToInt": ToInt,
        "True": True,
        "False": False,
    }
    try:
        return eval(expr_str, {"__builtins__": {}}, safe_env)
    except Exception as err:
        logger.error("Failed to evaluate SMT expression '%s': %s", expr_str, err)
        raise SMTExpressionSyntaxError(
            f"Invalid SMT expression '{expr_str}': {err}"
        ) from err

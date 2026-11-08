from __future__ import annotations

import logging
import random
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from app.schemas import (
    AutonomousPolicyGraph,
    InferredVariable,
    TelemetryEvaluationResult,
    TelemetryOutputDirective,
    VariableRole,
    VariableSort,
)
from app.services.smt.smt_helpers import (
    native_max,
    native_min,
    native_num_not,
    native_ord_not,
)

logger = logging.getLogger(__name__)


class TopologicalDAGRuntime:
    """High-frequency, JIT-compiled topological evaluation runtime for autonomous policy graphs."""

    def __init__(
        self,
        graph: AutonomousPolicyGraph,
        param_overrides: dict[str, float] | None = None,
    ) -> None:
        param_overrides = param_overrides or None
        self.graph = graph
        self.param_values: dict[str, float] = {}
        self.compiled_steps: list[tuple[str, Callable[[dict[str, Any]], Any]]] = []
        self.latencies_us: deque[float] = deque(maxlen=1000)
        self.last_state: dict[str, float | int | bool] = {}
        self.reload_graph(graph, param_overrides=param_overrides)

    def reload_graph(
        self,
        graph: AutonomousPolicyGraph,
        param_overrides: dict[str, float] | None = None,
    ) -> None:
        """Hot-reloads graph topology and JIT compiles all derived node formulas."""
        param_overrides = param_overrides or {}
        self.graph = graph
        self.param_values = {
            k: float(v.default_value)
            for k, v in graph.variables.items()
            if v.role == VariableRole.PARAMETER
        }
        if param_overrides:
            self.param_values.update(param_overrides)

        self.compiled_steps = []
        for target_id in graph.topological_order:
            if target_id in graph.equations:
                eq = graph.equations[target_id]
                py_fn = self._compile_smt_to_python_fn(eq.smt_expression)
                self.compiled_steps.append((target_id, py_fn))

        logger.info(
            "Reloaded runtime DAG: %d equations compiled in topological order",
            len(self.compiled_steps),
        )

    @staticmethod
    def _compile_smt_to_python_fn(
        smt_expr: str,
    ) -> Callable[[dict[str, Any]], Any]:
        """Compiles Z3 symbolic expression string into an optimized Python callable."""
        code_obj = compile(smt_expr, "<smt_dag_node>", "eval")
        env_helpers = {
            "And": lambda *args: all(bool(a) for a in args),
            "Or": lambda *args: any(bool(a) for a in args),
            "Not": lambda a: not bool(a),
            "If": lambda cond, t_val, f_val: t_val if bool(cond) else f_val,
            "z3_min": native_min,
            "z3_max": native_max,
            "num_not": native_num_not,
            "ord_not": native_ord_not,
            "RealVal": float,
            "IntVal": int,
            "BoolVal": bool,
            "ToReal": float,
            "ToInt": int,
            "True": True,
            "False": False,
        }
        return lambda state_dict: eval(
            code_obj, {"__builtins__": {}}, {**env_helpers, "v": state_dict}
        )

    def _generate_variable_value(
        self, v: InferredVariable, stress_spike: bool
    ) -> float | int | bool:
        mn = v.min_bound
        mx = v.max_bound
        if v.sort == VariableSort.INT:
            return (
                random.randint(int(mx) - 1, int(mx))
                if stress_spike
                else random.randint(int(mn), max(int(mn), int(mx) - 1))
            )
        if v.sort == VariableSort.REAL:
            val = (
                random.uniform(mn + 0.65 * (mx - mn), mx)
                if stress_spike
                else random.uniform(mn, mn + 0.55 * (mx - mn))
            )
            return round(val, 2)
        return stress_spike

    def generate_synthetic_telemetry(self) -> dict[str, float | int | bool]:
        """Generates a random telemetry packet strictly bounded by primary INPUT variables."""
        packet: dict[str, float | int | bool] = {}
        stress_spike = random.random() < 0.25
        for vid, v in self.graph.variables.items():
            if v.role == VariableRole.INPUT:
                packet[vid] = self._generate_variable_value(v, stress_spike)
        return packet

    @staticmethod
    def _is_elevated_state(
        val: Any, target_id: str, var_spec: InferredVariable
    ) -> bool:
        if not isinstance(val, (int, float)):
            return False
        if var_spec.sort == VariableSort.INT and val > 0:
            return True
        is_capacity_metric = any(
            w in target_id for w in ("capacity", "feasibility", "quality")
        )
        return var_spec.sort == VariableSort.REAL and is_capacity_metric and val < 50.0

    def _format_output_directives(
        self, state: dict[str, Any]
    ) -> dict[str, TelemetryOutputDirective]:
        outputs: dict[str, TelemetryOutputDirective] = {}
        for vid, v in self.graph.variables.items():
            if v.role == VariableRole.OUTPUT:
                raw_v = state.get(vid, v.default_value)
                lbl = (
                    v.ordinal_levels.get(int(raw_v), str(raw_v))
                    if v.ordinal_levels
                    else f"{raw_v}%"
                )
                outputs[vid] = TelemetryOutputDirective(
                    human_name=v.human_name,
                    value=raw_v,
                    label=lbl,
                )
        return outputs

    def evaluate_telemetry(
        self, input_telemetry: dict[str, float | int | bool]
    ) -> TelemetryEvaluationResult:
        """Executes a single fast-path pass through the compiled DAG."""
        t0 = time.perf_counter_ns()
        state: dict[str, Any] = {
            v.var_id: v.default_value for v in self.graph.variables.values()
        }
        state.update(self.param_values)
        state.update(input_telemetry)
        active_lineage: list[str] = []

        for target_id, fn in self.compiled_steps:
            val = fn(state)
            state[target_id] = val
            v_spec = self.graph.variables[target_id]
            if self._is_elevated_state(val, target_id, v_spec):
                active_lineage.append(target_id)

        latency_us = round((time.perf_counter_ns() - t0) / 1000.0, 2)
        self.latencies_us.append(latency_us)
        self.last_state = state

        outputs_formatted = self._format_output_directives(state)
        return TelemetryEvaluationResult(
            latency_us=latency_us,
            outputs=outputs_formatted,
            elevated_lineage_nodes=active_lineage,
            full_state=state,
        )

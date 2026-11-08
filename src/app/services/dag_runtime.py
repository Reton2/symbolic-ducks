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

    def generate_synthetic_telemetry(self) -> dict[str, float | int | bool]:
        """Generates a realistic telemetry packet modeling market microstructure.

        Most ticks (~85%) exhibit nominal operation with realistic micro-fluctuations
        around default values. Approximately 15% of ticks model focused, domain-specific
        stress events (e.g. market volatility, liquidity drought, or infrastructure latency)
        allowing autonomous policy directives to dynamically escalate and de-escalate.
        """
        packet: dict[str, float | int | bool] = {}
        is_stress = random.random() < 0.15
        stress_theme = (
            random.choice(["volatility", "connectivity", "liquidity", "drawdown"])
            if is_stress
            else None
        )

        for vid, v in self.graph.variables.items():
            if v.role != VariableRole.INPUT:
                continue

            def_val = v.default_value
            mn, mx = v.min_bound, v.max_bound

            if v.sort == VariableSort.REAL:
                span = mx - mn
                def_num = float(def_val)
                if (
                    is_stress
                    and stress_theme == "volatility"
                    and any(k in vid for k in ("vix", "volatility"))
                ):
                    val = random.uniform(32.0, min(mx, 55.0))
                elif (
                    is_stress
                    and stress_theme == "volatility"
                    and any(k in vid for k in ("return", "momentum"))
                ):
                    val = random.uniform(max(mn, -10.0), -2.0)
                elif is_stress and stress_theme == "liquidity" and ("depth" in vid):
                    val = max(mn, def_num * random.uniform(0.15, 0.40))
                elif (
                    is_stress
                    and stress_theme == "liquidity"
                    and ("imbalance" in vid or "spread" in vid)
                ):
                    val = random.uniform(def_num * 1.5, min(mx, def_num * 3.5))
                elif (
                    is_stress
                    and stress_theme == "drawdown"
                    and any(k in vid for k in ("drawdown", "slippage", "drift"))
                ):
                    val = random.uniform(def_num * 2.5, min(mx, def_num * 5.0))
                else:
                    # Natural continuous Gaussian perturbation around nominal default (~2%)
                    scale = 0.02 * (span if 0 < span < 1000 else max(1.0, abs(def_num)))
                    noise = random.gauss(0, scale)
                    val = min(mx, max(mn, def_num + noise))
                packet[vid] = round(val, 2)

            elif v.sort == VariableSort.INT:
                def_int = int(def_val)
                if (
                    is_stress
                    and stress_theme == "connectivity"
                    and any(
                        k in vid for k in ("heartbeat", "connection", "fix", "latency")
                    )
                    or is_stress
                    and stress_theme == "drawdown"
                    and any(k in vid for k in ("margin", "inventory", "deficit"))
                    or is_stress
                    and stress_theme == "liquidity"
                    and any(
                        k in vid
                        for k in (
                            "liquidity_stress",
                            "congestion",
                            "throttling",
                            "cancellation",
                        )
                    )
                ):
                    packet[vid] = random.choice([1, 2])
                elif random.random() < 0.02:
                    # Isolated minor transient pulse
                    packet[vid] = min(int(mx), def_int + 1)
                else:
                    packet[vid] = def_int

            else:
                packet[vid] = bool(def_val)

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
                lbl = str(raw_v)
                if v.ordinal_levels:
                    try:
                        int_k = int(raw_v)
                        lbl = (
                            v.ordinal_levels.get(int_k)
                            or v.ordinal_levels.get(str(int_k))
                            or str(raw_v)
                        )
                    except (ValueError, TypeError):
                        lbl = v.ordinal_levels.get(raw_v, str(raw_v))
                else:
                    try:
                        lbl = f"{float(raw_v):.1f}%"
                    except (ValueError, TypeError):
                        lbl = f"{raw_v}%"
                outputs[vid] = TelemetryOutputDirective(
                    human_name=v.human_name,
                    value=raw_v,
                    label=lbl,
                )
        return outputs

    def evaluate_telemetry(
        self, input_telemetry: dict[str, float | int | bool | str]
    ) -> TelemetryEvaluationResult:
        """Executes a single fast-path pass through the compiled DAG."""
        t0 = time.perf_counter_ns()
        state: dict[str, Any] = {
            v.var_id: v.default_value for v in self.graph.variables.values()
        }
        state.update(self.param_values)

        for k, v in input_telemetry.items():
            if v is None:
                continue
            if k not in self.graph.variables:
                state[k] = v
                continue
            v_spec = self.graph.variables[k]
            if v_spec.ordinal_levels and isinstance(v, str):
                matched_idx: int | None = None
                raw_str = v.strip()
                for idx, lvl_name in v_spec.ordinal_levels.items():
                    if (
                        str(lvl_name).strip().upper() == raw_str.upper()
                        or str(idx) == raw_str
                    ):
                        matched_idx = int(idx)
                        break
                if matched_idx is not None:
                    state[k] = matched_idx
                else:
                    try:
                        state[k] = int(float(raw_str))
                    except (ValueError, TypeError):
                        state[k] = v
            elif v_spec.sort == VariableSort.INT and isinstance(v, (str, float)):
                try:
                    state[k] = int(float(v))
                except (ValueError, TypeError):
                    state[k] = v
            elif v_spec.sort == VariableSort.REAL and isinstance(v, str):
                try:
                    state[k] = float(v)
                except (ValueError, TypeError):
                    state[k] = v
            elif v_spec.sort == VariableSort.BOOL and isinstance(v, str):
                state[k] = v.strip().lower() in ("true", "1", "sat", "t")
            else:
                state[k] = v

        active_lineage: list[str] = []

        for target_id, fn in self.compiled_steps:
            try:
                val = fn(state)
            except Exception as err:
                logger.debug("DAG evaluation fallback for %s: %s", target_id, err)
                val = self.graph.variables[target_id].default_value
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

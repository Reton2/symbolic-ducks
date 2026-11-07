import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime
from typing import Any

import numpy as np

from app.domains.catalogue import generate_domain_event
from app.schemas.schemas import (
    BacktestMetrics,
    LogicalGroupNode,
    PolicyDocumentBundle,
    PolicyItem,
    RedTeamOccurrence,
)


class GroundDataPlaneEngine:
    def __init__(self, bundle: PolicyDocumentBundle):
        self.bundle = bundle
        self.params = {k: v.value for k, v in bundle.parameters.items()}
        self.compiled_policies: list[
            tuple[PolicyItem, Callable[[dict[str, Any]], bool]]
        ] = []
        self._compile_all()

        self.live_windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=5))
        self.latencies_us = deque(maxlen=2000)
        self.decision_counts = {
            "PASS": 0,
            "INTERCEPT": 0,
            "STEP_UP_AUTH": 0,
            "ALLOW_OVERRIDE": 0,
        }
        self.redteam_occurrences: deque[RedTeamOccurrence] = deque(maxlen=25)

        self.historical_corpus: list[dict[str, Any]] = []
        self.reseed_corpus(bundle.domain_key, count=1500)

    def reseed_corpus(self, domain_key: str, count: int = 1500):
        self.historical_corpus = [
            generate_domain_event(domain_key) for _ in range(count)
        ]

    def hot_reload(self, new_bundle: PolicyDocumentBundle):
        if new_bundle.domain_key != self.bundle.domain_key:
            self.reseed_corpus(new_bundle.domain_key, count=1500)
            self.redteam_occurrences.clear()
        self.bundle = new_bundle.model_copy(deep=True)
        self.params = {k: v.value for k, v in self.bundle.parameters.items()}
        self._compile_all()

    def _compile_all(self):
        active = [p for p in self.bundle.policies if p.enabled]
        sorted_pols = sorted(active, key=lambda r: r.priority, reverse=True)
        self.compiled_policies = [
            (p, self._compile_node(p.root_node, self.params)) for p in sorted_pols
        ]

    def _compile_node(
        self, node: Any, params: dict[str, Any]
    ) -> Callable[[dict[str, Any]], bool]:
        if (
            isinstance(node, LogicalGroupNode)
            or getattr(node, "node_type", None) == "LOGICAL"
        ):
            sub_fns = [self._compile_node(c, params) for c in node.children]
            if node.logic_op == "AND":
                return lambda ev: all(f(ev) for f in sub_fns)
            if node.logic_op == "OR":
                return lambda ev: any(f(ev) for f in sub_fns)
            if node.logic_op == "NOT":
                return lambda ev: not sub_fns[0](ev)

        lf, op = node.left_field, node.operator
        if node.right_field:
            rf, rm = node.right_field, node.right_multiplier
            if op == ">":
                return lambda ev: ev.get(lf, 0) > (ev.get(rf, 0) * rm)
            if op == ">=":
                return lambda ev: ev.get(lf, 0) >= (ev.get(rf, 0) * rm)
            if op == "<":
                return lambda ev: ev.get(lf, 0) < (ev.get(rf, 0) * rm)
        else:
            rv = (
                params.get(node.param_ref, node.literal_value)
                if node.param_ref
                else node.literal_value
            )
            if op == "==":
                return lambda ev, rv=rv: ev.get(lf) == rv
            if op == "!=":
                return lambda ev, rv=rv: ev.get(lf) != rv
            if op == ">":
                return lambda ev, rv=rv: ev.get(lf, 0) > rv
            if op == ">=":
                return lambda ev, rv=rv: ev.get(lf, 0) >= rv
            if op == "<":
                return lambda ev, rv=rv: ev.get(lf, 0) < rv
            if op == "<=":
                return lambda ev, rv=rv: ev.get(lf, 0) <= rv
            if op == "IN":
                s_set = set(rv if isinstance(rv, list) else [rv])
                return lambda ev, s_set=s_set: ev.get(lf) in s_set
        return lambda ev: False

    def evaluate_live_event(
        self, raw_event: dict[str, Any], source: str = "STREAM"
    ) -> dict[str, Any]:
        t0 = time.perf_counter_ns()
        ev = dict(raw_event)
        ent = str(ev.get(self.bundle.entity_key, "global"))
        pf = self.bundle.primary_value_field
        wf = self.bundle.window_value_field

        win = self.live_windows[ent]
        win.append(float(ev.get(pf, 0.0)))
        if source != "Z3_RED_TEAM_SYNTH":
            ev[wf] = round(sum(win), 2)

        decision = "PASS"
        triggered_policy = None
        for pol, fn in self.compiled_policies:
            if fn(ev):
                decision = pol.action
                triggered_policy = pol.policy_id
                break

        latency_us = round((time.perf_counter_ns() - t0) / 1000.0, 2)
        self.latencies_us.append(latency_us)
        self.decision_counts[decision] = self.decision_counts.get(decision, 0) + 1

        # Full-Circle Breach Detection: If a Red-Team or anomalous attack passed without INTERCEPT, log & synthesize NL patch
        is_attack = bool(ev.get("_is_anomalous_attack", False))
        if source == "Z3_RED_TEAM_SYNTH" or (is_attack and decision == "PASS"):
            breach = decision == "PASS"
            patch_nl = self._synthesize_patch_prose(ev) if breach else None
            occ = RedTeamOccurrence(
                occurrence_id=f"occ_{str(uuid.uuid4())[:6]}",
                timestamp=datetime.utcnow().strftime("%H:%M:%S"),
                source="Z3_RED_TEAM_SYNTH"
                if source == "Z3_RED_TEAM_SYNTH"
                else "LIVE_ANOMALY_ESCAPEE",
                event_payload={k: v for k, v in ev.items() if not k.startswith("_")},
                decision=decision,
                triggered_policy=triggered_policy,
                breach_detected=breach,
                suggested_nl_patch=patch_nl,
            )
            self.redteam_occurrences.appendleft(occ)

        return {
            "event": ev,
            "decision": decision,
            "triggered_policy": triggered_policy,
            "latency_us": latency_us,
        }

    def _synthesize_patch_prose(self, ev: dict[str, Any]) -> str:
        """Creates a ready-to-compile natural language policy recommendation that blocks the escaped event."""
        pf = self.bundle.primary_value_field
        val = float(ev.get(pf, 50000.0))
        tighter_limit = round(val * 0.90, 0)
        if self.bundle.domain_key == "quant_risk":
            sp = round(max(1.0, float(ev.get("spread_bps", 12.0)) - 1.0), 1)
            return f"Intercept any order where {pf} exceeds {tighter_limit} while spread_bps is greater than {sp}."
        else:
            rk = round(max(0.1, float(ev.get("risk_score", 0.75)) - 0.05), 2)
            return f"Intercept transfer when {pf} exceeds {tighter_limit} and risk_score exceeds {rk}."

    def run_shadow_backtest(
        self, candidate_bundle: PolicyDocumentBundle
    ) -> BacktestMetrics:
        params = {k: v.value for k, v in candidate_bundle.parameters.items()}
        active = sorted(
            [p for p in candidate_bundle.policies if p.enabled],
            key=lambda r: r.priority,
            reverse=True,
        )
        compiled = [(p, self._compile_node(p.root_node, params)) for p in active]

        sim_windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=5))
        latencies = []
        counts = {"PASS": 0, "INTERCEPT": 0}
        tp, total_attacks, fp, total_benign = 0, 0, 0, 0

        pf = candidate_bundle.primary_value_field
        wf = candidate_bundle.window_value_field
        ek = candidate_bundle.entity_key

        for raw in self.historical_corpus:
            t0 = time.perf_counter_ns()
            ev = dict(raw)
            win = sim_windows[str(ev.get(ek, "global"))]
            win.append(float(ev.get(pf, 0.0)))
            ev[wf] = round(sum(win), 2)

            decision = "PASS"
            for pol, fn in compiled:
                if fn(ev):
                    decision = pol.action
                    break
            latencies.append((time.perf_counter_ns() - t0) / 1000.0)
            counts[decision] = counts.get(decision, 0) + 1

            if ev.get("_is_anomalous_attack"):
                total_attacks += 1
                if decision == "INTERCEPT":
                    tp += 1
            else:
                total_benign += 1
                if decision == "INTERCEPT":
                    fp += 1

        n = max(1, len(self.historical_corpus))
        arr = np.array(latencies) if latencies else np.array([0.5])
        return BacktestMetrics(
            sample_size=len(self.historical_corpus),
            intercept_count=counts.get("INTERCEPT", 0),
            pass_count=counts.get("PASS", 0),
            blast_radius_pct=round((counts.get("INTERCEPT", 0) / n) * 100.0, 2),
            simulated_fraud_recall_pct=round((tp / max(1, total_attacks)) * 100.0, 2),
            false_positive_rate_pct=round((fp / max(1, total_benign)) * 100.0, 2),
            p50_latency_us=round(float(np.percentile(arr, 50)), 2),
            p99_latency_us=round(float(np.percentile(arr, 99)), 2),
        )

    def compare_bundles(self, candidate_bundle: PolicyDocumentBundle) -> dict[str, Any]:
        base_m = self.run_shadow_backtest(self.bundle)
        cand_m = self.run_shadow_backtest(candidate_bundle)
        return {
            "baseline": base_m.model_dump(),
            "candidate": cand_m.model_dump(),
            "deltas": {
                "blast_radius_pct_delta": round(
                    cand_m.blast_radius_pct - base_m.blast_radius_pct, 2
                ),
                "fraud_recall_pct_delta": round(
                    cand_m.simulated_fraud_recall_pct
                    - base_m.simulated_fraud_recall_pct,
                    2,
                ),
                "false_positive_pct_delta": round(
                    cand_m.false_positive_rate_pct - base_m.false_positive_rate_pct, 2
                ),
            },
        }

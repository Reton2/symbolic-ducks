import json
import sys
from pathlib import Path

from app.control.html_exporter import export_standalone_html
from app.control.nl_engine import sync_bundle_prose
from app.control.smt_engine import Z3PolicyProver
from app.data.runtime import GroundDataPlaneEngine
from app.domains.catalogue import get_default_bundles


def main():
    config_path = Path("policies/candidate_config.json")
    raw_cfg = (
        json.loads(config_path.read_text())
        if config_path.exists()
        else {"domain_key": "quant_risk", "parameter_overrides": {}}
    )
    domain_key = raw_cfg.get("domain_key", "quant_risk")
    overrides = raw_cfg.get("parameter_overrides", {})

    bundles = get_default_bundles()
    base_bundle = bundles[domain_key].model_copy(deep=True)
    cand_bundle = bundles[domain_key].model_copy(deep=True)

    for k, val in overrides.items():
        if k in cand_bundle.parameters:
            cand_bundle.parameters[k].value = val
    cand_bundle = sync_bundle_prose(cand_bundle)

    prover = Z3PolicyProver(cand_bundle)
    z3_res = prover.run_full_verification_suite()

    engine = GroundDataPlaneEngine(base_bundle)
    comp = engine.compare_bundles(cand_bundle)
    b_m, c_m, d_m = comp["baseline"], comp["candidate"], comp["deltas"]

    Path("policy_explainability_graph.html").write_text(
        export_standalone_html(cand_bundle, z3_res)
    )

    status_str = (
        "✅ VERIFIED"
        if z3_res["overall_status"] == "VERIFIED"
        else "❌ FAILED Z3 PROOF"
    )
    lines = [
        f"### 🛡️ PolicyGuard Full-Circle GitOps Report — {status_str}",
        f"**Domain Track:** `{cand_bundle.title}` (`{cand_bundle.bundle_id}`)",
        "",
        "#### 1. Bidirectional Natural Language Policy Diff",
    ]
    for b_p, c_p in zip(base_bundle.policies, cand_bundle.policies, strict=True):
        if b_p.natural_language_text != c_p.natural_language_text:
            lines.append(f"- **{c_p.policy_id} ({c_p.name}):**")
            lines.append(f"  - **Baseline:** `{b_p.natural_language_text}`")
            lines.append(f"  - **Candidate:** `{c_p.natural_language_text}`")
        else:
            lines.append(
                f"- **{c_p.policy_id} ({c_p.name}):** *Unchanged* (`{c_p.natural_language_text}`)"
            )

    lines.extend(
        [
            "",
            "#### 2. Shadow Backtest Telemetry Deltas (N=1,500 Historical Replay)",
            "| Metric | Baseline | Candidate PR | Delta |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Blast Radius (Intercept %)** | {b_m['blast_radius_pct']}% | {c_m['blast_radius_pct']}% | `{d_m['blast_radius_pct_delta']:+.2f}%` |",
            f"| **Anomaly / Fraud Recall** | {b_m['simulated_fraud_recall_pct']}% | {c_m['simulated_fraud_recall_pct']}% | `{d_m['fraud_recall_pct_delta']:+.2f}%` |",
            f"| **False Positive Rate** | {b_m['false_positive_rate_pct']}% | {c_m['false_positive_rate_pct']}% | `{d_m['false_positive_pct_delta']:+.2f}%` |",
            f"| **Hot-Path Latency (P50 / P99)** | {b_m['p50_latency_us']}µs / {b_m['p99_latency_us']}µs | {c_m['p50_latency_us']}µs / {c_m['p99_latency_us']}µs | `<10µs SLA` |",
            "",
            "#### 3. Z3 Formal Verification & Anti-Smurfing Audit",
        ]
    )
    if not z3_res["issues"]:
        lines.append(
            "- **Satisfiability, Axiom Bounds & Anti-Structuring:** `UNSAT` for exploits (Mathematically Verified)."
        )
    else:
        for iss in z3_res["issues"]:
            lines.append(
                f"- ❌ **{iss['type']} ({iss['policy_id']}):** {iss['detail']}"
            )

    report = "\n".join(lines)
    Path("pr_governance_report.md").write_text(report)
    print(report)

    if z3_res["overall_status"] != "VERIFIED":
        sys.exit(1)


if __name__ == "__main__":
    main()

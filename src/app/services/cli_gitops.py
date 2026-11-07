from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

from app.control.autoformalisation import DeepAutoformalizer
from app.control.html_exporter import export_graph_html
from app.control.smt_engine import DeepSMTSolverEngine
from app.data.runtime import TopologicalDAGRuntime
from app.mandate import AMM_QRM_2026_V5_TEXT
from app.schemas.schemas import AutonomousPolicyGraph, GraphVerificationReport

logger = logging.getLogger("app.services.cli_gitops")


def load_candidate_config() -> dict[str, float]:
    """Loads parameter overrides from candidate_config.json."""
    config_path = Path("policies/candidate_config.json")
    if not config_path.is_file():
        logger.info("No candidate_config.json found; running with default parameters")
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        overrides = data.get("parameter_overrides", {})
        return {
            k: float(v) for k, v in overrides.items() if isinstance(v, (int, float))
        }
    except Exception as err:
        logger.warning(
            "Failed to parse candidate_config.json (%s); using defaults", err
        )
        return {}


def format_markdown_report(
    graph: AutonomousPolicyGraph,
    verification: GraphVerificationReport,
    overrides: dict[str, float],
    runtime_latency_us: float,
) -> str:
    """Formats an executive GitOps PR governance markdown report."""
    status_icon = (
        "✅ VERIFIED" if verification.status == "VERIFIED" else "❌ UNVERIFIED"
    )
    lines = [
        f"### 🛡️ PolicyGuard Autonomous SMT GitOps Report — {status_icon}",
        f"**Graph ID:** `{graph.graph_id}` | **Title:** `{graph.title}`",
        f"**Discovered Variables:** `{len(graph.variables)}` | **Topological Equations:** `{len(graph.equations)}`",
        "",
        "#### 1. Candidate Parameter Configuration",
    ]
    if overrides:
        lines.append("| Parameter Key | Candidate PR Value |")
        lines.append("| :--- | :--- |")
        for k, v in overrides.items():
            lines.append(f"| `{k}` | `{v}` |")
    else:
        lines.append("*Operating with inferred baseline parameters.*")

    lines.extend(
        [
            "",
            "#### 2. Z3 SMT Formal Reachability Proofs",
            f"- **Base Domain Consistency:** `{'SAT (Consistent)' if verification.consistent else 'UNSAT (Contradiction)'}`",
            f"- **Evaluated Directives:** {len(verification.reachability_proofs)} state proofs",
            f"- **Hot-Path DAG Evaluation Latency:** `{runtime_latency_us:.2f} µs`",
        ]
    )

    if verification.dead_state_warnings:
        lines.append("\n**⚠️ Dead Logic Warnings:**")
        for warn in verification.dead_state_warnings:
            lines.append(f"- {warn}")
    else:
        lines.append(
            "- ✅ **All output directive states proven mathematically reachable.**"
        )

    return "\n".join(lines)


async def run_gitops_audit() -> int:
    """Orchestrates autonomous autoformalization, Z3 SMT audit, and report generation."""
    logger.info("Starting PolicyGuard Autonomous GitOps audit...")
    overrides = load_candidate_config()

    autoformalizer = DeepAutoformalizer.from_env()
    graph = await autoformalizer.autoformalize_document(AMM_QRM_2026_V5_TEXT)

    solver = DeepSMTSolverEngine(graph, overrides)
    verification = solver.verify_full_graph()

    runtime = TopologicalDAGRuntime(graph, overrides)
    telemetry = runtime.generate_synthetic_telemetry()
    eval_result = runtime.evaluate_telemetry(telemetry)

    html_content = export_graph_html(graph, verification)
    Path("policy_explainability_graph.html").write_text(html_content, encoding="utf-8")

    report_md = format_markdown_report(
        graph, verification, overrides, eval_result.latency_us
    )
    Path("pr_governance_report.md").write_text(report_md, encoding="utf-8")
    print(report_md)

    return 0 if verification.status == "VERIFIED" else 1


def main() -> None:
    exit_code = asyncio.run(run_gitops_audit())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import logging
from typing import Any

from app.schemas.schemas import (
    AutonomousPolicyGraph,
    GraphVerificationReport,
    LogicalGroupNode,
    PolicyDocumentBundle,
)

logger = logging.getLogger("app.control.html_exporter")

GRAPH_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PolicyGuard Logic Graph — __TITLE__</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 p-6 font-sans">
  <div class="max-w-7xl mx-auto">
    <header class="mb-6 flex justify-between items-center border-b border-slate-800 pb-4">
      <div>
        <h1 class="text-2xl font-bold text-emerald-400">__TITLE__</h1>
        <p class="text-xs text-slate-400 mt-1">
          Graph ID: <span class="font-mono text-slate-300">__GRAPH_ID__</span> |
          Sentences: __SENTENCE_COUNT__ |
          Topological Nodes: __TOPO_COUNT__
        </p>
      </div>
      <div id="verif-badge"></div>
    </header>

    <div id="verif-panel" class="mb-6"></div>

    <div class="grid grid-cols-12 gap-6">
      <div class="col-span-4 space-y-4">
        <div class="bg-slate-900 border border-slate-800 rounded p-4">
          <h2 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
            Variables (__VARS_COUNT__)
          </h2>
          <div id="vars-list" class="space-y-2 max-h-[600px] overflow-y-auto pr-1"></div>
        </div>
      </div>

      <div class="col-span-8 space-y-4">
        <div class="bg-slate-900 border border-slate-800 rounded p-4">
          <h2 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
            Topological Equations (__EQS_COUNT__)
          </h2>
          <div id="equations-list" class="space-y-3 max-h-[600px] overflow-y-auto pr-1"></div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const variables = __VARS_JSON__;
    const equations = __EQS_JSON__;
    const topo = __TOPO_JSON__;
    const verif = __VERIF_JSON__;

    function escapeHtml(str) {
      if (!str) return '';
      const div = document.createElement('div');
      div.textContent = str;
      return div.innerHTML;
    }

    // Render formal verification status
    if (verif && verif.status) {
      const isOk = verif.status === 'VERIFIED';
      document.getElementById('verif-badge').innerHTML = isOk
        ? '<span class="px-3 py-1 rounded text-xs font-mono bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold">✅ Z3 SMT VERIFIED</span>'
        : '<span class="px-3 py-1 rounded text-xs font-mono bg-rose-950 text-rose-300 border border-rose-800 font-bold">⚠️ SMT AUDIT ISSUES</span>';

      const warnings = verif.dead_state_warnings || [];
      document.getElementById('verif-panel').innerHTML = `
        <div class="p-3 bg-slate-900 border ${isOk ? 'border-emerald-800/60' : 'border-rose-800/60'} rounded text-xs">
          <div class="flex justify-between items-center font-bold mb-1">
            <span class="${isOk ? 'text-emerald-400' : 'text-rose-400'}">Formal Z3 SMT Proof Status: ${verif.status}</span>
            <span class="font-mono text-slate-400">${(verif.reachability_proofs || []).length} Reachability Proofs</span>
          </div>
          ${warnings.length > 0 ? warnings.map(w => `<div class="text-amber-400 mt-1">• ${escapeHtml(w)}</div>`).join('') : '<div class="text-slate-400">All output directive states proven mathematically reachable under active parameters.</div>'}
        </div>
      `;
    }

    document.getElementById('vars-list').innerHTML = Object.values(variables).map(v => {
      const roleBadge = v.role === 'INPUT'
        ? 'bg-sky-950 text-sky-400 border border-sky-800'
        : (v.role === 'OUTPUT' ? 'bg-rose-950 text-rose-400 border border-rose-800' : 'bg-emerald-950 text-emerald-400 border border-emerald-800');
      return `
        <div class="p-2.5 bg-slate-950 border border-slate-800 rounded text-xs">
          <div class="flex justify-between items-center font-mono">
            <span class="font-bold text-slate-200">${escapeHtml(v.var_id)}</span>
            <span class="px-1.5 py-0.5 rounded text-[10px] ${roleBadge}">${v.role}</span>
          </div>
          <div class="text-slate-300 mt-1">${escapeHtml(v.human_name)}</div>
          <div class="text-[10px] text-slate-500 mt-0.5 font-mono">
            Sort: ${v.sort} | Layer: ${v.layer_index} | Bounds: [${v.min_bound}, ${v.max_bound}]
          </div>
        </div>
      `;
    }).join('');

    document.getElementById('equations-list').innerHTML = topo.filter(id => equations[id]).map(id => {
      const eq = equations[id];
      const targetVar = variables[id] || {};
      const deps = (eq.dependencies || []).map(d => `<span class="px-1.5 py-0.5 bg-slate-900 border border-slate-700 rounded text-slate-300 text-[10px] font-mono">${escapeHtml(d)}</span>`).join(' ');
      return `
        <div class="p-3 bg-slate-950 border border-slate-800 rounded">
          <div class="flex justify-between items-center mb-1.5">
            <span class="font-mono text-xs font-bold text-emerald-400">${escapeHtml(eq.target_var)} <span class="text-slate-400 font-normal">(${escapeHtml(targetVar.human_name || '')})</span></span>
            <span class="text-[10px] font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">Layer ${targetVar.layer_index || 0}</span>
          </div>
          <div class="font-mono text-xs bg-slate-900 p-2.5 rounded text-amber-300 border border-slate-800/80 overflow-x-auto whitespace-pre">${escapeHtml(eq.smt_expression)}</div>
          <div class="text-[11px] text-slate-400 mt-2 flex items-center gap-1.5 flex-wrap">
            <span>Dependencies:</span>
            ${deps || '<span class="text-slate-600 font-mono">None</span>'}
          </div>
        </div>
      `;
    }).join('');
  </script>
</body>
</html>
"""

STANDALONE_BUNDLE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PolicyGuard Provenance Graph — __TITLE__</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 p-6 font-sans">
  <div class="max-w-7xl mx-auto">
    <header class="mb-6 flex justify-between items-center border-b border-slate-800 pb-4">
      <div>
        <h1 class="text-2xl font-bold text-emerald-400 mb-1">__TITLE__</h1>
        <p class="text-xs text-slate-400">Click any AST node or Natural Language Policy to cross-highlight provenance links.</p>
      </div>
      <div id="z3-badge"></div>
    </header>

    <div id="z3-audit-panel" class="mb-6"></div>

    <div class="grid grid-cols-12 gap-6">
      <div id="pols" class="col-span-5 space-y-3"></div>
      <div id="nodes" class="col-span-7 space-y-2 bg-slate-900 p-4 rounded border border-slate-800"></div>
    </div>
  </div>

  <script>
    const pols = __POLS_JSON__;
    const graph = __GRAPH_JSON__;
    const z3Report = __Z3_REPORT_JSON__;

    // Render Z3 verification status badge & audit panel
    const isVerified = z3Report && (z3Report.overall_status === 'VERIFIED' || z3Report.status === 'VERIFIED');
    const badgeEl = document.getElementById('z3-badge');
    if (badgeEl) {
      badgeEl.innerHTML = isVerified
        ? '<span class="px-3 py-1 rounded text-xs font-mono bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold">✅ Z3 SMT VERIFIED</span>'
        : '<span class="px-3 py-1 rounded text-xs font-mono bg-rose-950 text-rose-300 border border-rose-800 font-bold">❌ Z3 PROOF ISSUES</span>';
    }

    const auditEl = document.getElementById('z3-audit-panel');
    if (auditEl && z3Report && Object.keys(z3Report).length > 0) {
      const issues = z3Report.issues || [];
      const warnings = z3Report.dead_state_warnings || [];
      auditEl.innerHTML = `
        <div class="p-3 bg-slate-900 border ${isVerified ? 'border-emerald-800/60' : 'border-rose-800/60'} rounded text-xs">
          <div class="flex justify-between items-center mb-1 font-bold">
            <span class="${isVerified ? 'text-emerald-400' : 'text-rose-400'}">Z3 Formal Verification & Proof Audit: ${z3Report.overall_status || z3Report.status || 'UNAUDITED'}</span>
            <span class="font-mono text-slate-400">${issues.length} Issues Detected</span>
          </div>
          ${issues.length === 0 && warnings.length === 0 ? '<p class="text-slate-400">Zero contradictions, vacuous policies, or anti-structuring bypasses detected.</p>' : ''}
          ${issues.map(iss => `<div class="text-rose-400 mt-1 font-mono">• <strong>${iss.type || 'ISSUE'} (${iss.policy_id || ''}):</strong> ${iss.detail || ''}</div>`).join('')}
          ${warnings.map(w => `<div class="text-amber-400 mt-1 font-mono">• ${w}</div>`).join('')}
        </div>
      `;
    }

    function selectPol(pid) {
      document.querySelectorAll('[data-pid]').forEach(el => {
        el.classList.toggle('ring-2', el.dataset.pid === pid);
        el.classList.toggle('ring-emerald-400', el.dataset.pid === pid);
      });
    }

    document.getElementById('pols').innerHTML = pols.map(p => `
      <div data-pid="${p.policy_id}" onclick="selectPol('${p.policy_id}')" class="cursor-pointer p-3 bg-slate-900 border border-slate-800 rounded">
        <div class="text-xs font-mono text-emerald-400 font-bold">${p.policy_id} — ${p.name}</div>
        <div class="text-xs text-slate-200 mt-1">${p.natural_language_text}</div>
      </div>`).join('');

    document.getElementById('nodes').innerHTML = graph.nodes.map(n => {
      const cls = n.type === 'POLICY_ROOT'
        ? 'ml-0 font-bold text-rose-300'
        : (n.type === 'LOGICAL' ? 'ml-6 text-sky-300' : 'ml-12 text-emerald-300');
      return `
        <div data-pid="${n.policy_id}" onclick="selectPol('${n.policy_id}')" class="cursor-pointer p-2 bg-slate-950 border border-slate-800 rounded text-xs font-mono ${cls}">
          ${n.label} <span class="float-right text-amber-400">↗ ${n.policy_id}</span>
        </div>`;
    }).join('');
  </script>
</body>
</html>
"""


def export_graph_html(
    graph: AutonomousPolicyGraph,
    verification: GraphVerificationReport | None = None,
) -> str:
    """Exports an interactive standalone HTML visualization of an AutonomousPolicyGraph,

    displaying topological layers, variables, and symbolic SMT formulas.
    """
    logger.info("Exporting standalone HTML logic graph for %s", graph.graph_id)
    vars_json = json.dumps({k: v.model_dump() for k, v in graph.variables.items()})
    eqs_json = json.dumps({k: v.model_dump() for k, v in graph.equations.items()})
    topo_json = json.dumps(graph.topological_order)
    verif_json = json.dumps(verification.model_dump() if verification else {})

    html = (
        GRAPH_HTML_TEMPLATE.replace("__TITLE__", graph.title)
        .replace("__GRAPH_ID__", graph.graph_id)
        .replace("__SENTENCE_COUNT__", str(graph.sentence_count))
        .replace("__TOPO_COUNT__", str(len(graph.topological_order)))
        .replace("__VARS_COUNT__", str(len(graph.variables)))
        .replace("__EQS_COUNT__", str(len(graph.equations)))
        .replace("__VARS_JSON__", vars_json)
        .replace("__EQS_JSON__", eqs_json)
        .replace("__TOPO_JSON__", topo_json)
        .replace("__VERIF_JSON__", verif_json)
    )
    return html


def build_provenance_graph_data(
    bundle: PolicyDocumentBundle,
    param_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Legacy bundle provenance graph extraction."""
    overrides = param_overrides or {}
    params = {k: v.value for k, v in bundle.parameters.items()}
    if overrides:
        params.update(overrides)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def _walk(node: Any, parent_id: str, pol_id: str) -> None:
        if (
            isinstance(node, LogicalGroupNode)
            or getattr(node, "node_type", None) == "LOGICAL"
        ):
            nodes.append(
                {
                    "id": node.node_id,
                    "parent_id": parent_id,
                    "policy_id": pol_id,
                    "type": "LOGICAL",
                    "label": f"{node.logic_op} Gate ({node.node_id})",
                }
            )
            edges.append({"from": parent_id, "to": node.node_id})
            for child in node.children:
                _walk(child, node.node_id, pol_id)
        else:
            val = (
                params.get(node.param_ref, node.literal_value)
                if node.param_ref
                else node.literal_value
            )
            nodes.append(
                {
                    "id": node.node_id,
                    "parent_id": parent_id,
                    "policy_id": pol_id,
                    "type": "COMPARISON",
                    "param_ref": node.param_ref,
                    "label": f"{node.left_field} {node.operator} {val}"
                    + (f" ({{{{{node.param_ref}}}}})" if node.param_ref else ""),
                }
            )
            edges.append({"from": parent_id, "to": node.node_id})

    for pol in bundle.policies:
        root_id = f"ROOT_{pol.policy_id}"
        nodes.append(
            {
                "id": root_id,
                "parent_id": None,
                "policy_id": pol.policy_id,
                "type": "POLICY_ROOT",
                "enabled": pol.enabled,
                "label": f"[{pol.action}] {pol.name} ({pol.policy_id})",
            }
        )
        _walk(pol.root_node, root_id, pol.policy_id)

    return {"nodes": nodes, "edges": edges}


def export_standalone_html(
    bundle: PolicyDocumentBundle,
    z3_report: dict[str, Any] | None = None,
) -> str:
    """Exports interactive HTML provenance graph visualizing AST nodes, policy bindings,

    and formal Z3 verification audit findings.
    """
    logger.info("Exporting standalone AST HTML graph for bundle %s", bundle.bundle_id)
    report = z3_report or {}
    graph = build_provenance_graph_data(bundle)
    pols_json = json.dumps([p.model_dump() for p in bundle.policies])
    graph_json = json.dumps(graph)
    z3_json = json.dumps(report)

    html = (
        STANDALONE_BUNDLE_TEMPLATE.replace("__TITLE__", bundle.title)
        .replace("__POLS_JSON__", pols_json)
        .replace("__GRAPH_JSON__", graph_json)
        .replace("__Z3_REPORT_JSON__", z3_json)
    )
    return html

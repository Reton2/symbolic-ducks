import json
from typing import Any

from app.schemas.schemas import LogicalGroupNode, PolicyDocumentBundle


def build_provenance_graph_data(
    bundle: PolicyDocumentBundle, param_overrides: dict[str, Any] = None
) -> dict[str, Any]:
    params = {k: v.value for k, v in bundle.parameters.items()}
    if param_overrides:
        params.update(param_overrides)

    nodes, edges = [], []

    def _walk(node: Any, parent_id: str, pol_id: str):
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
    bundle: PolicyDocumentBundle, z3_report: dict[str, Any]
) -> str:
    graph = build_provenance_graph_data(bundle)
    policies_json = json.dumps([p.model_dump() for p in bundle.policies])
    graph_json = json.dumps(graph)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>PolicyGuard Provenance Graph — {bundle.title}</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-slate-950 text-slate-100 p-6 font-sans">
  <h1 class="text-2xl font-bold text-emerald-400 mb-2">{bundle.title} — Provenance & Logic Graph</h1>
  <p class="text-xs text-slate-400 mb-6">Click any AST node or Natural Language Policy to cross-highlight provenance links.</p>
  <div class="grid grid-cols-12 gap-6">
    <div id="pols" class="col-span-5 space-y-3"></div>
    <div id="nodes" class="col-span-7 space-y-2 bg-slate-900 p-4 rounded border border-slate-800"></div>
  </div>
  <script>
    const pols = {policies_json}; const graph = {graph_json};
    function selectPol(pid) {{
      document.querySelectorAll('[data-pid]').forEach(el => {{
        el.classList.toggle('ring-2', el.dataset.pid === pid);
        el.classList.toggle('ring-emerald-400', el.dataset.pid === pid);
      }});
    }}
    document.getElementById('pols').innerHTML = pols.map(p => `
      <div data-pid="${{p.policy_id}}" onclick="selectPol('${{p.policy_id}}')" class="cursor-pointer p-3 bg-slate-900 border border-slate-800 rounded">
        <div class="text-xs font-mono text-emerald-400 font-bold">${{p.policy_id}} — ${{p.name}}</div>
        <div class="text-xs text-slate-200 mt-1">${{p.natural_language_text}}</div>
      </div>`).join('');
    document.getElementById('nodes').innerHTML = graph.nodes.map(n => `
      <div data-pid="${{n.policy_id}}" onclick="selectPol('${{n.policy_id}}')" class="cursor-pointer p-2 bg-slate-950 border border-slate-800 rounded text-xs font-mono ${"{"}n.type==='POLICY_ROOT'?'ml-0 font-bold text-rose-300':(n.type==='LOGICAL'?'ml-6 text-sky-300':'ml-12 text-emerald-300'){"}"}">
        ${{n.label}} <span class="float-right text-amber-400">↗ ${{n.policy_id}}</span>
      </div>`).join('');
  </script>
</body></html>"""

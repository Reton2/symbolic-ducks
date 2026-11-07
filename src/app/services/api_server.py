import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from app.control.html_exporter import (
    build_provenance_graph_data,
    export_standalone_html,
)
from app.control.nl_engine import BidirectionalNLEngine, sync_bundle_prose
from app.control.smt_engine import Z3PolicyProver
from app.data.runtime import GroundDataPlaneEngine
from app.domains.catalogue import generate_domain_event, get_default_bundles
from app.schemas.schemas import PolicyDocumentBundle, UpdateRequestItem
from app.services.bus import ClusterStateBus

app = FastAPI(title="PolicyGuard: Full-Circle Neuro-Symbolic Policy OS")

BUNDLES = get_default_bundles()
active_domain = os.getenv("ACTIVE_DOMAIN", "quant_risk")
production_bundle: PolicyDocumentBundle = BUNDLES[active_domain].model_copy(deep=True)
working_bundle: PolicyDocumentBundle = BUNDLES[active_domain].model_copy(deep=True)

nl_engine = BidirectionalNLEngine()
data_engine = GroundDataPlaneEngine(production_bundle)
bus = ClusterStateBus()

update_requests: list[UpdateRequestItem] = []
stream_state = {"rate_per_sec": 6, "clients": set()}


def _on_cluster_bundle_update(bundle_dict: dict[str, Any]):
    global production_bundle
    production_bundle = PolicyDocumentBundle.model_validate(bundle_dict)
    data_engine.hot_reload(production_bundle)


@app.on_event("startup")
async def on_startup():
    await bus.connect(on_bundle_update=_on_cluster_bundle_update)
    if os.getenv("SERVICE_ROLE", "ALL") in ("ALL", "DATA_PLANE"):
        asyncio.create_task(live_stream_worker())


async def live_stream_worker():
    while True:
        if stream_state["clients"] and stream_state["rate_per_sec"] > 0:
            raw_ev = generate_domain_event(production_bundle.domain_key)
            eval_res = data_engine.evaluate_live_event(raw_ev, source="STREAM")
            await _broadcast_ws(
                {
                    "type": "LIVE_EVENT",
                    "result": eval_res,
                    "counts": data_engine.decision_counts,
                    "occurrences": [
                        o.model_dump()
                        for o in list(data_engine.redteam_occurrences)[:8]
                    ],
                }
            )
        await asyncio.sleep(1.0 / max(1, stream_state["rate_per_sec"]))


async def _broadcast_ws(payload: dict[str, Any]):
    dead = set()
    for ws in stream_state["clients"]:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    stream_state["clients"] -= dead


class NLIterateRequest(BaseModel):
    natural_language_text: str
    policy_id: str | None = None
    policy_name: str | None = None
    auto_heal_smurfing: bool = True


class ParameterUpdateRequest(BaseModel):
    parameter_overrides: dict[str, Any]


class StateInferenceRequest(BaseModel):
    partial_state: dict[str, Any]


class CreatePRRequest(BaseModel):
    author: str = "Risk_Lead_Edin"
    summary: str


@app.get("/")
async def serve_ui():
    return FileResponse("static/index.html")


@app.get("/api/workspace")
async def get_workspace():
    prover = Z3PolicyProver(working_bundle)
    z3_report = prover.run_full_verification_suite()
    graph = build_provenance_graph_data(working_bundle)
    metrics_comp = data_engine.compare_bundles(working_bundle)
    return {
        "service_role": os.getenv("SERVICE_ROLE", "ALL (CLUSTER_READY)"),
        "secrets_manager": os.getenv("SECRETS_PROVIDER", "DOPPLER_ZERO_TRUST"),
        "available_domains": list(BUNDLES.keys()),
        "production_bundle": production_bundle.model_dump(),
        "working_bundle": working_bundle.model_dump(),
        "provenance_graph": graph,
        "z3_verification": z3_report,
        "metrics_comparison": metrics_comp,
        "update_requests": [u.model_dump() for u in update_requests],
        "redteam_occurrences": [
            o.model_dump() for o in data_engine.redteam_occurrences
        ],
    }


@app.post("/api/domain/{domain_key}")
async def switch_domain(domain_key: str):
    global production_bundle, working_bundle
    if domain_key not in BUNDLES:
        raise HTTPException(400, "Unknown domain")
    production_bundle = BUNDLES[domain_key].model_copy(deep=True)
    working_bundle = BUNDLES[domain_key].model_copy(deep=True)
    data_engine.hot_reload(production_bundle)
    await bus.publish_bundle(production_bundle.model_dump())
    return await get_workspace()


@app.post("/api/policy/nl-iterate")
async def iterate_policy_from_nl(req: NLIterateRequest):
    """Compiles new or edited Natural Language policy prose into AST + Parameters + CEGIS Z3 Auto-Heal."""
    global working_bundle
    working_bundle = await nl_engine.compile_nl_into_bundle(
        working_bundle,
        raw_text=req.natural_language_text,
        policy_id=req.policy_id,
        policy_name=req.policy_name,
        auto_heal_smurfing=req.auto_heal_smurfing,
    )
    return await get_workspace()


@app.post("/api/policy/toggle/{policy_id}")
async def toggle_policy(policy_id: str):
    for p in working_bundle.policies:
        if p.policy_id == policy_id:
            p.enabled = not p.enabled
    return await get_workspace()


@app.delete("/api/policy/{policy_id}")
async def delete_policy(policy_id: str):
    working_bundle.policies = [
        p for p in working_bundle.policies if p.policy_id != policy_id
    ]
    working_bundle.parameters = {
        k: v for k, v in working_bundle.parameters.items() if v.policy_id != policy_id
    }
    return await get_workspace()


@app.post("/api/config/update-params")
async def update_working_parameters(req: ParameterUpdateRequest):
    """Updates working parameters, bidirectionally regenerates natural language policy prose, and re-runs Z3 + Backtest."""
    global working_bundle
    for k, val in req.parameter_overrides.items():
        if k in working_bundle.parameters:
            working_bundle.parameters[k].value = val
    working_bundle = sync_bundle_prose(working_bundle)
    return await get_workspace()


@app.post("/api/z3/infer-state")
async def infer_symbolic_state(req: StateInferenceRequest):
    prover = Z3PolicyProver(working_bundle)
    return prover.infer_input_states(req.partial_state)


@app.post("/api/redteam/inject")
async def inject_z3_redteam_attack():
    """Synthesizes a boundary-pushing payload via Z3 and injects it directly into the live Data Plane stream."""
    prover = Z3PolicyProver(production_bundle)
    synth = prover.synthesize_red_team_bypass()
    if synth["status"] == "BYPASS_SYNTHESIZED":
        eval_res = data_engine.evaluate_live_event(
            synth["payload"], source="Z3_RED_TEAM_SYNTH"
        )
        await _broadcast_ws(
            {
                "type": "LIVE_EVENT",
                "result": eval_res,
                "counts": data_engine.decision_counts,
                "occurrences": [
                    o.model_dump() for o in list(data_engine.redteam_occurrences)[:8]
                ],
            }
        )
    return await get_workspace()


@app.post("/api/update-requests/create")
async def create_update_request(req: CreatePRRequest):
    """Stages current working bundle changes into an auditable Update Request (In-App PR & GitOps export)."""
    prover = Z3PolicyProver(working_bundle)
    z3_rep = prover.run_full_verification_suite()
    metrics_comp = data_engine.compare_bundles(working_bundle)

    prod_map = {
        p.policy_id: p.natural_language_text for p in production_bundle.policies
    }
    work_map = {p.policy_id: p.natural_language_text for p in working_bundle.policies}
    all_ids = sorted(set(prod_map.keys()) | set(work_map.keys()))
    nl_diff = []
    for pid in all_ids:
        b_txt = prod_map.get(pid, "[NONE — NEW POLICY]")
        c_txt = work_map.get(pid, "[DELETED]")
        if b_txt != c_txt:
            nl_diff.append(
                {"policy_id": pid, "baseline_prose": b_txt, "candidate_prose": c_txt}
            )
    if not nl_diff:
        nl_diff.append(
            {
                "policy_id": "CONFIG_SYNC",
                "baseline_prose": "Baseline active",
                "candidate_prose": "Candidate verified",
            }
        )

    ur = UpdateRequestItem(
        request_id=f"PR-{len(update_requests) + 101}",
        timestamp=datetime.utcnow().strftime("%H:%M:%S UTC"),
        author=req.author,
        summary=req.summary,
        candidate_bundle=working_bundle.model_copy(deep=True),
        nl_diff=nl_diff,
        z3_report=z3_rep,
        metrics_comparison=metrics_comp,
    )
    update_requests.insert(0, ur)

    # Also write candidate_config.json to disk so GitHub Actions CLI can cross-reference it immediately
    Path("policies").mkdir(exist_ok=True)
    Path("policies/candidate_config.json").write_text(
        json.dumps(
            {
                "domain_key": working_bundle.domain_key,
                "parameter_overrides": {
                    k: v.value for k, v in working_bundle.parameters.items()
                },
            },
            indent=2,
        )
    )

    return await get_workspace()


@app.post("/api/update-requests/{request_id}/approve")
async def approve_and_hot_reload(request_id: str):
    """Approves an Update Request and broadcasts zero-downtime hot-reload across Data Plane microservices."""
    global production_bundle, working_bundle
    for ur in update_requests:
        if ur.request_id == request_id:
            if ur.z3_report["overall_status"] != "VERIFIED":
                raise HTTPException(
                    400,
                    "Cannot merge Update Request that failed Z3 Formal Verification",
                )
            ur.status = "APPROVED_MERGED"
            production_bundle = ur.candidate_bundle.model_copy(deep=True)
            working_bundle = ur.candidate_bundle.model_copy(deep=True)
            data_engine.hot_reload(production_bundle)
            await bus.publish_bundle(production_bundle.model_dump())
            break
    return await get_workspace()


@app.get("/api/export/html", response_class=HTMLResponse)
async def export_html_graph():
    prover = Z3PolicyProver(working_bundle)
    return HTMLResponse(
        content=export_standalone_html(
            working_bundle, prover.run_full_verification_suite()
        )
    )


@app.post("/api/rate/{rate}")
async def set_rate(rate: int):
    stream_state["rate_per_sec"] = max(0, min(rate, 120))
    return {"rate_per_sec": stream_state["rate_per_sec"]}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    stream_state["clients"].add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        stream_state["clients"].discard(ws)

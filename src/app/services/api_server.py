from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse

from app.control.autoformalisation import DeepAutoformalizer
from app.control.smt_engine import DeepSMTSolverEngine
from app.data.runtime import TopologicalDAGRuntime
from app.mandate import AMM_QRM_2026_V5_TEXT
from app.schemas.schemas import (
    AutonomousPolicyGraph,
    CounterfactualRequest,
    IngestDocumentRequest,
    SolveForInputsRequest,
    UpdateParamsRequest,
)

logger = logging.getLogger("app.services.api_server")


class AppState:
    """Encapsulated runtime container avoiding implicit global state."""

    def __init__(self) -> None:
        self.autoformalizer: DeepAutoformalizer = DeepAutoformalizer.from_env()
        self.graph: AutonomousPolicyGraph | None = None
        self.runtime: TopologicalDAGRuntime | None = None
        self.param_overrides: dict[str, float] = {}
        self.clients: set[WebSocket] = set()
        self.rate_per_sec: int = 4
        self.streamer_task: asyncio.Task[None] | None = None


async def telemetry_streamer(state: AppState) -> None:
    """Background task streaming synthetic high-frequency DAG telemetry ticks to WebSocket clients."""
    logger.info("Starting telemetry streamer loop (%d ticks/sec)", state.rate_per_sec)
    try:
        while True:
            if state.clients and state.rate_per_sec > 0 and state.runtime:
                pkt = state.runtime.generate_synthetic_telemetry()
                res = state.runtime.evaluate_telemetry(pkt)
                payload = {"type": "TELEMETRY_TICK", "data": res.model_dump()}
                dead: set[WebSocket] = set()
                for ws in list(state.clients):
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        dead.add(ws)
                if dead:
                    state.clients -= dead
                    logger.debug("Pruned %d dead WebSocket connections", len(dead))
            await asyncio.sleep(1.0 / max(1, state.rate_per_sec))
    except asyncio.CancelledError:
        logger.info("Telemetry streamer loop cancelled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan context manager initializing policy graph and background tasks."""
    logger.info("PolicyGuard OS booting up...")
    state = AppState()
    app.state.app_state = state

    state.graph = await state.autoformalizer.autoformalize_document(
        AMM_QRM_2026_V5_TEXT
    )
    state.param_overrides = {
        k: float(v.default_value)
        for k, v in state.graph.variables.items()
        if v.role == "PARAMETER"
    }
    state.runtime = TopologicalDAGRuntime(
        state.graph, param_overrides=state.param_overrides
    )
    state.streamer_task = asyncio.create_task(telemetry_streamer(state))
    logger.info("PolicyGuard OS initialized (Graph ID: %s)", state.graph.graph_id)

    yield

    logger.info("Shutting down PolicyGuard OS...")
    if state.streamer_task:
        state.streamer_task.cancel()
    for ws in list(state.clients):
        await ws.close()


app = FastAPI(
    title="PolicyGuard Deep Neuro-Symbolic SMT OS",
    lifespan=lifespan,
)


def get_app_state() -> AppState:
    state = getattr(app.state, "app_state", None)
    if not state or state.graph is None or state.runtime is None:
        raise HTTPException(status_code=503, detail="System initializing")
    return state


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/api/state")
async def get_system_state():
    state = get_app_state()
    solver = DeepSMTSolverEngine(state.graph, state.param_overrides)
    verification = solver.verify_full_graph()
    logger.debug("System state retrieved: verification=%s", verification.status)
    return {
        "graph": state.graph.model_dump(),
        "param_overrides": state.param_overrides,
        "verification": verification.model_dump(),
        "smtlib2_preview": solver.export_smtlib2()[:4000],
    }


@app.post("/api/params/update")
async def update_parameters(req: UpdateParamsRequest):
    state = get_app_state()
    state.param_overrides.update(req.param_overrides)
    for k, val in req.param_overrides.items():
        if k in state.graph.variables:
            state.graph.variables[k].default_value = val
    state.runtime.reload_graph(state.graph, state.param_overrides)
    logger.info("Updated %d parameter overrides", len(req.param_overrides))
    return await get_system_state()


@app.post("/api/smt/solve-inputs")
async def solve_for_inputs_endpoint(req: SolveForInputsRequest):
    """Abductive Z3 solving: synthesizes foundational telemetry values from desired target constraints."""
    state = get_app_state()
    solver = DeepSMTSolverEngine(state.graph, state.param_overrides)
    res = solver.solve_for_inputs(req.target_constraints)

    if res.status == "SATISFIABLE" and res.solved_state:
        solved_inputs = {k: v.value for k, v in res.solved_state.INPUT.items()}
        eval_res = state.runtime.evaluate_telemetry(solved_inputs)
        payload = {"type": "SOLVED_INJECTION", "data": eval_res.model_dump()}
        dead: set[WebSocket] = set()
        for ws in list(state.clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        state.clients -= dead
        logger.info(
            "Injected solved telemetry to %d WebSocket clients", len(state.clients)
        )

    return res.model_dump()


@app.post("/api/smt/counterfactual")
async def counterfactual_endpoint(req: CounterfactualRequest):
    """MaxSMT counterfactual search: finds minimal input interventions."""
    state = get_app_state()
    solver = DeepSMTSolverEngine(state.graph, state.param_overrides)
    current_in = {
        k: float(state.runtime.last_state.get(k, v.default_value))
        for k, v in state.graph.variables.items()
        if v.role == "INPUT"
    }
    res = solver.solve_counterfactual_repair(
        current_in, req.desired_output_var, req.desired_val
    )
    logger.info("Counterfactual repair status: %s", res.status)
    return res.model_dump()


@app.get("/api/smtlib2", response_class=PlainTextResponse)
async def download_smtlib2():
    state = get_app_state()
    solver = DeepSMTSolverEngine(state.graph, state.param_overrides)
    return solver.export_smtlib2()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    state = get_app_state()
    state.clients.add(ws)
    logger.info("WebSocket connected (active: %d)", len(state.clients))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        state.clients.discard(ws)
        logger.info("WebSocket disconnected (remaining: %d)", len(state.clients))


@app.post("/api/ingest-document")
async def ingest_unstructured_document(req: IngestDocumentRequest):
    """Ingests unstructured policy text, infers causal graph topology, and hot-swaps Z3."""
    state = get_app_state()
    logger.info(
        "Ingesting unstructured document (%d chars, shuffle=%s)",
        len(req.raw_text),
        req.shuffle_sentences,
    )
    state.graph = await state.autoformalizer.autoformalize_document(
        req.raw_text, shuffle_sentences=req.shuffle_sentences
    )
    state.param_overrides = {
        k: float(v.default_value)
        for k, v in state.graph.variables.items()
        if v.role == "PARAMETER"
    }
    state.runtime.reload_graph(state.graph, state.param_overrides)
    logger.info(
        "Hot-swapped runtime with newly inferred graph %s", state.graph.graph_id
    )
    return await get_system_state()

import logging

from fastapi import APIRouter, Depends, WebSocket

from app.dependency.state import AppState, get_app_state
from app.schemas import EvaluateTelemetryRequest, TelemetryEvaluationResult
from app.services.dag_runtime import TopologicalDAGRuntime

telemetry_router = APIRouter(prefix="/telemetry")

logger = logging.getLogger(__name__)


@telemetry_router.post("/evaluate", response_model=TelemetryEvaluationResult)
async def evaluate_telemetry_endpoint(
    req: EvaluateTelemetryRequest,
    state: AppState = Depends(get_app_state),
) -> TelemetryEvaluationResult:
    """Evaluates arbitrary input telemetry values and broadcasts to live clients."""
    if state.runtime is None:
        state.runtime = TopologicalDAGRuntime(state.graph, state.param_overrides)
    res = state.runtime.evaluate_telemetry(req.telemetry)
    payload = {"type": "MANUAL_INJECTION", "data": res.model_dump(mode="json")}
    dead: set[WebSocket] = set()
    for ws in list(state.clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    state.clients -= dead
    return res

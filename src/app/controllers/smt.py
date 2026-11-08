import logging

from fastapi import APIRouter, Depends, WebSocket

from app.dependency.dependency import get_smt_solver
from app.dependency.state import AppState, get_app_state
from app.schemas import (
    AbductiveSolveResult,
    AbductiveSolveStatus,
    CounterfactualRequest,
    CounterfactualResult,
    SolveForInputsRequest,
    VariableRole,
)
from app.services.smt.smt_engine import DeepSMTSolverEngine

smt_router = APIRouter(prefix="/smt")

logger = logging.getLogger(__name__)


@smt_router.post("/solve-inputs", response_model=AbductiveSolveResult)
async def solve_for_inputs_endpoint(
    req: SolveForInputsRequest,
    state: AppState = Depends(get_app_state),
    solver: DeepSMTSolverEngine = Depends(get_smt_solver),
) -> AbductiveSolveResult:
    res = solver.solve_for_inputs(req.target_constraints)
    solved = res.status == AbductiveSolveStatus.SATISFIABLE and res.solved_state

    if not solved:
        return res

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
    logger.info("Injected solved telemetry to %d WebSocket clients", len(state.clients))


@smt_router.post("/counterfactual", response_model=CounterfactualResult)
async def counterfactual_endpoint(
    req: CounterfactualRequest,
    state: AppState = Depends(get_app_state),
    solver: DeepSMTSolverEngine = Depends(get_smt_solver),
) -> CounterfactualResult:
    current_in = {
        k: float(state.runtime.last_state.get(k, v.default_value))
        for k, v in state.graph.variables.items()
        if v.role == VariableRole.INPUT
    }
    res = solver.solve_counterfactual_repair(
        current_in, req.desired_output_var, req.desired_val
    )
    logger.info("Counterfactual repair status: %s", res.status)
    return res

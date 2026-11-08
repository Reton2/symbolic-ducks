import logging

from fastapi import APIRouter, Depends

from app.controllers.state import get_system_state
from app.dependency.dependency import get_smt_solver
from app.dependency.state import AppState, get_app_state
from app.schemas import SystemStateResponse, UpdateParamsRequest
from app.services.smt.smt_engine import DeepSMTSolverEngine

params_router = APIRouter(prefix="/params")

logger = logging.getLogger(__name__)


@params_router.post("/update", response_model=SystemStateResponse)
async def update_parameters(
    req: UpdateParamsRequest,
    state: AppState = Depends(get_app_state),
    solver: DeepSMTSolverEngine = Depends(get_smt_solver),
) -> SystemStateResponse:
    state.param_overrides.update(req.param_overrides)
    if state.graph is not None:
        for k, val in req.param_overrides.items():
            if k in state.graph.variables:
                state.graph.variables[k].default_value = val
    if state.runtime is not None:
        state.runtime.reload_graph(state.graph, state.param_overrides)
    logger.info("Updated %d parameter overrides", len(req.param_overrides))
    return await get_system_state(state=state, solver=solver)

from fastapi import Depends

from app.dependency.state import AppState, get_app_state
from app.services.autoformalisation import DeepAutoformalizer
from app.services.dag_runtime import TopologicalDAGRuntime
from app.services.smt.smt_engine import DeepSMTSolverEngine


async def get_autoformalizer(
    state: AppState = Depends(get_app_state),
) -> DeepAutoformalizer:
    return state.autoformalizer


async def get_runtime(
    state: AppState = Depends(get_app_state),
) -> TopologicalDAGRuntime:
    return state.runtime


async def get_smt_solver(
    state: AppState = Depends(get_app_state),
) -> DeepSMTSolverEngine:
    return DeepSMTSolverEngine(state.graph, state.param_overrides)

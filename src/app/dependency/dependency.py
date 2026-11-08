from fastapi import Depends

from app.control.autoformalisation import DeepAutoformalizer
from app.control.smt_engine import DeepSMTSolverEngine
from app.data.runtime import TopologicalDAGRuntime
from app.dependency.state import AppState, get_app_state


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

import logging

from fastapi import APIRouter, Depends

from app.controllers.state import get_system_state
from app.dependency.dependency import get_autoformalizer
from app.dependency.state import AppState, get_app_state
from app.schemas import IngestDocumentRequest, SystemStateResponse, VariableRole
from app.services.autoformalisation import DeepAutoformalizer
from app.services.dag_runtime import TopologicalDAGRuntime
from app.services.smt.smt_engine import DeepSMTSolverEngine

document_router = APIRouter(prefix="/document")

logger = logging.getLogger(__name__)


@document_router.post("/ingest", response_model=SystemStateResponse)
async def ingest_unstructured_document(
    req: IngestDocumentRequest,
    state: AppState = Depends(get_app_state),
    autoformalizer: DeepAutoformalizer = Depends(get_autoformalizer),
) -> SystemStateResponse:
    """Ingests unstructured policy text, infers causal graph topology, and hot-swaps Z3."""
    logger.info(
        "Ingesting unstructured document (%d chars, shuffle=%s)",
        len(req.raw_text),
        req.shuffle_sentences,
    )
    state.graph = await autoformalizer.autoformalize_document(
        req.raw_text, shuffle_sentences=req.shuffle_sentences
    )
    state.param_overrides = {
        k: float(v.default_value)
        for k, v in state.graph.variables.items()
        if v.role == VariableRole.PARAMETER
    }
    if state.runtime is not None:
        state.runtime.reload_graph(state.graph, state.param_overrides)
    else:
        state.runtime = TopologicalDAGRuntime(state.graph, state.param_overrides)
    logger.info(
        "Hot-swapped runtime with newly inferred graph %s", state.graph.graph_id
    )
    fresh_solver = DeepSMTSolverEngine(state.graph, state.param_overrides)
    return await get_system_state(state=state, solver=fresh_solver)

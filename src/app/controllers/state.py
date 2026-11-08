import logging

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.dependency.dependency import get_smt_solver
from app.dependency.state import AppState, get_app_state
from app.schemas import SystemStateResponse
from app.services.html_exporter import export_graph_html
from app.services.smt.smt_engine import DeepSMTSolverEngine

state_router = APIRouter(prefix="/state")

logger = logging.getLogger(__name__)


@state_router.get("", response_model=SystemStateResponse)
async def get_system_state(
    state: AppState = Depends(get_app_state),
    solver: DeepSMTSolverEngine = Depends(get_smt_solver),
) -> SystemStateResponse:
    verification = solver.verify_full_graph()
    logger.debug("System state retrieved: verification=%s", verification.status)
    return SystemStateResponse(
        graph=state.graph,
        param_overrides=state.param_overrides,
        verification=verification,
        smtlib2_preview=solver.export_smtlib2()[:4000],
    )


@state_router.get("/smtlib2", response_class=PlainTextResponse)
async def download_smtlib2(
    solver: DeepSMTSolverEngine = Depends(get_smt_solver),
) -> str:
    return solver.export_smtlib2()


@state_router.get("/graph.html", response_class=HTMLResponse)
@state_router.get("/html", response_class=HTMLResponse)
async def view_graph_html(
    state: AppState = Depends(get_app_state),
    solver: DeepSMTSolverEngine = Depends(get_smt_solver),
) -> HTMLResponse:
    """Exports interactive standalone HTML visualization of the active AutonomousPolicyGraph."""
    verification = solver.verify_full_graph()
    html_content = export_graph_html(state.graph, verification=verification)
    return HTMLResponse(content=html_content)

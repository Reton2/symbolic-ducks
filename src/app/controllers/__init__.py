from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.controllers.document import document_router
from app.controllers.params import params_router
from app.controllers.root import root_router
from app.controllers.smt import smt_router
from app.controllers.state import download_smtlib2, state_router, view_graph_html
from app.controllers.telemetry import telemetry_router
from app.controllers.ws import ws_router

__all__ = [
    "document_router",
    "params_router",
    "root_router",
    "smt_router",
    "state_router",
    "telemetry_router",
    "ws_router",
]

api_router = APIRouter(prefix="/api")
api_router.include_router(document_router)
api_router.include_router(params_router)
api_router.include_router(smt_router)
api_router.include_router(state_router)
api_router.include_router(telemetry_router)
api_router.add_api_route(
    "/smtlib2", download_smtlib2, response_class=PlainTextResponse, methods=["GET"]
)
api_router.add_api_route(
    "/graph.html", view_graph_html, response_class=HTMLResponse, methods=["GET"]
)

root_router.include_router(api_router)
root_router.include_router(ws_router)

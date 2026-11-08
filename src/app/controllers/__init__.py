from fastapi import APIRouter

from app.controllers.document import document_router
from app.controllers.params import params_router
from app.controllers.root import root_router
from app.controllers.smt import smt_router
from app.controllers.state import state_router
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

root_router.include_router(api_router)
root_router.include_router(ws_router)

import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.dependency.state import AppState, get_app_state

ws_router = APIRouter()

logger = logging.getLogger(__name__)


@ws_router.websocket("/ws")
async def ws_endpoint(
    ws: WebSocket,
    state: AppState = Depends(get_app_state),
) -> None:
    await ws.accept()
    state.clients.add(ws)
    logger.info("WebSocket connected (active: %d)", len(state.clients))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        state.clients.discard(ws)
        logger.info("WebSocket disconnected (remaining: %d)", len(state.clients))

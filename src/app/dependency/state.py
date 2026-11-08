import asyncio
import contextlib
import logging
from typing import Any

from fastapi import HTTPException, WebSocket

from app.control.autoformalisation import DeepAutoformalizer
from app.data.runtime import TopologicalDAGRuntime
from app.mandate import AMM_QRM_2026_V5_TEXT
from app.schemas import AutonomousPolicyGraph, VariableRole

logger = logging.getLogger(__name__)


class AppState:
    def __init__(self) -> None:
        self.autoformalizer: DeepAutoformalizer = DeepAutoformalizer.from_env()
        self.graph: AutonomousPolicyGraph | None = None
        self.runtime: TopologicalDAGRuntime | None = None
        self.param_overrides: dict[str, float] = {}
        self.clients: set[WebSocket] = set()
        self.rate_per_sec: int = 4
        self.streamer_task: asyncio.Task[None] | None = None

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self.clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        if dead:
            self.clients -= dead
            logger.debug("Pruned %d dead WebSocket connections", len(dead))

    async def start_streamer(self) -> None:
        logger.info(
            "Starting telemetry streamer loop (%d ticks/sec)", self.rate_per_sec
        )
        try:
            while True:
                if self.clients and self.rate_per_sec > 0 and self.runtime:
                    pkt = self.runtime.generate_synthetic_telemetry()
                    res = self.runtime.evaluate_telemetry(pkt)
                    await self.broadcast(
                        {"type": "TELEMETRY_TICK", "data": res.model_dump()}
                    )
                await asyncio.sleep(1.0 / max(1, self.rate_per_sec))
        except asyncio.CancelledError:
            logger.info("Telemetry streamer loop cancelled")

    async def startup(self) -> None:
        logger.info("PolicyGuard OS booting up...")
        self.graph = await self.autoformalizer.autoformalize_document(
            AMM_QRM_2026_V5_TEXT
        )
        self.param_overrides = {
            k: float(v.default_value)
            for k, v in self.graph.variables.items()
            if v.role == VariableRole.PARAMETER
        }
        self.runtime = TopologicalDAGRuntime(
            self.graph, param_overrides=self.param_overrides
        )
        self.streamer_task = asyncio.create_task(self.start_streamer())
        logger.info("PolicyGuard OS initialized (Graph ID: %s)", self.graph.graph_id)

    async def shutdown(self) -> None:
        logger.info("Shutting down PolicyGuard OS...")
        if self.streamer_task:
            self.streamer_task.cancel()
        for ws in list(self.clients):
            with contextlib.suppress(Exception):
                await ws.close()
        self.clients.clear()


state = AppState()


async def get_app_state() -> AppState:
    if not state or state.graph is None or state.runtime is None:
        raise HTTPException(status_code=503, detail="System initializing")
    return state

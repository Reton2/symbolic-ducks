from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable
from typing import Any

import redis.asyncio as aioredis

from app.schemas.schemas import AutonomousPolicyGraph

logger = logging.getLogger("app.services.bus")


class ClusterStateBus:
    """Distributed Redis state synchronizer for multi-replica policy graph updates."""

    def __init__(self, redis_url: str = "") -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "")
        self.redis_client: aioredis.Redis | None = None
        self.channel = "policyguard:bundle_updates"
        self._subscriber_task: asyncio.Task[None] | None = None

    async def connect(
        self,
        on_graph_update: Callable[[dict[str, Any]], None] | None = None,
    ) -> bool:
        """Establishes connection to Redis cluster and attaches update subscriber loop."""
        if not self.redis_url:
            logger.info("REDIS_URL not configured; operating in local standalone mode")
            return False

        try:
            self.redis_client = aioredis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            logger.info("Connected to Redis cluster at %s", self.redis_url)
            if on_graph_update:
                self._subscriber_task = asyncio.create_task(
                    self._subscriber_loop(on_graph_update)
                )
            return True
        except Exception as err:
            logger.warning(
                "Redis connection failed: %s; fallback to standalone mode", err
            )
            self.redis_client = None
            return False

    async def publish_graph(self, graph: AutonomousPolicyGraph) -> None:
        """Serializes and broadcasts an active policy graph update to cluster replicas."""
        if not self.redis_client:
            return
        payload = json.dumps(graph.model_dump())
        try:
            await self.redis_client.set("policyguard:active_graph", payload)
            await self.redis_client.publish(self.channel, payload)
            logger.info(
                "Broadcasted active graph %s to channel %s",
                graph.graph_id,
                self.channel,
            )
        except Exception as err:
            logger.error("Failed to publish policy graph update to Redis: %s", err)

    async def _subscriber_loop(
        self, callback: Callable[[dict[str, Any]], None]
    ) -> None:
        assert self.redis_client is not None
        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(self.channel)
            logger.info("Subscribed to Redis channel %s", self.channel)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    logger.debug("Received cluster graph update message")
                    callback(data)
        except asyncio.CancelledError:
            logger.info("Redis subscriber loop cancelled")
        except Exception as err:
            logger.error("Redis subscriber error: %s", err, exc_info=True)

    async def close(self) -> None:
        """Gracefully closes Redis connection and cancels background subscriber."""
        if self._subscriber_task:
            self._subscriber_task.cancel()
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Closed Redis cluster connection")

import asyncio
import json
import os
from collections.abc import Callable
from typing import Any

import redis.asyncio as aioredis


class ClusterStateBus:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "")
        self.redis_client: aioredis.Redis | None = None
        self.channel = "policyguard:bundle_updates"

    async def connect(
        self, on_bundle_update: Callable[[dict[str, Any]], None] | None = None
    ):
        if not self.redis_url:
            return
        try:
            self.redis_client = aioredis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            if on_bundle_update:
                asyncio.create_task(self._subscriber_loop(on_bundle_update))
        except Exception:
            self.redis_client = None

    async def publish_bundle(self, bundle_dict: dict[str, Any]):
        payload = json.dumps(bundle_dict)
        if self.redis_client:
            await self.redis_client.set("policyguard:active_bundle", payload)
            await self.redis_client.publish(self.channel, payload)

    async def _subscriber_loop(self, callback: Callable[[dict[str, Any]], None]):
        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(self.channel)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    callback(data)
        except Exception:
            pass

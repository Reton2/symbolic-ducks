from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config.autoformalizer import AutoformalizerConfig
from app.schemas import AutonomousPolicyGraph
from app.services.autoformalisation.cache import (
    IntermediateStateStore,
    PolicyGraphCache,
)
from app.services.autoformalisation.pipeline import AgenticPolicyCompiler
from app.services.autoformalisation.sentence_reader import SentenceAtomizer

logger = logging.getLogger(__name__)


class DeepAutoformalizer:
    def __init__(
        self,
        config: AutoformalizerConfig | None = None,
        client: AsyncOpenAI | None = None,
        cache: PolicyGraphCache | None = None,
    ) -> None:
        self.config = config or AutoformalizerConfig.from_env()
        if client is not None:
            self.client: AsyncOpenAI | None = client
        elif self.config.api_key:
            self.client = AsyncOpenAI(
                api_key=self.config.api_key, base_url=self.config.base_url
            )
        else:
            self.client = None

        self.atomizer = SentenceAtomizer()
        self.cache = cache or PolicyGraphCache(
            cache_dir=self.config.cache_dir,
            enabled=self.config.enable_cache,
        )
        self.state_store = IntermediateStateStore(cache_dir=self.config.cache_dir)
        self.pipeline = AgenticPolicyCompiler(
            config=self.config,
            client=self.client,
            state_store=self.state_store,
        )

    @classmethod
    def from_defaults(cls) -> DeepAutoformalizer:
        return cls(config=AutoformalizerConfig.from_env())

    @classmethod
    def from_env(cls) -> DeepAutoformalizer:
        return cls(config=AutoformalizerConfig.from_env())

    @classmethod
    def with_client(
        cls,
        client: AsyncOpenAI,
        config: AutoformalizerConfig | None = None,
        cache: PolicyGraphCache | None = None,
    ) -> DeepAutoformalizer:
        cfg = config or AutoformalizerConfig.from_env()
        return cls(config=cfg, client=client, cache=cache)

    async def autoformalize_document(
        self,
        raw_text: str,
        use_cache: bool = True,
    ) -> AutonomousPolicyGraph:
        if use_cache:
            cached_graph = self.cache.get(raw_text)
            if cached_graph is not None:
                return cached_graph

        sentences = self.atomizer.atomize(raw_text)
        graph = await self.pipeline.compile_policy(raw_text, sentences)

        if use_cache:
            self.cache.put(raw_text, graph)
        return graph

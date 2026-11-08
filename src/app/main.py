from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.controllers import (
    root_router,
)
from app.dependency.state import state

logger = logging.getLogger("app")


def configure_logger(level_name: str = "INFO") -> None:
    numeric_level = getattr(logging, level_name.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(numeric_level)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    await state.startup()
    yield
    await state.shutdown()


app = FastAPI(
    title="PolicyGuard Deep Neuro-Symbolic SMT OS",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/packages", StaticFiles(directory="packages"), name="packages")

app.include_router(root_router)

"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import APP_VERSION
from app.api.router import api_router
from app.config import get_settings
from app.core.errors import ApiError, api_error_handler
from app.core.logging import configure_logging
from app.schemas.health import RootMetadata

settings = get_settings()
configure_logging()
logger = logging.getLogger("dr_robot.api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Log process lifecycle without exposing configuration secrets."""

    logger.info("Application startup", extra={"environment": settings.app_env})
    yield
    logger.info("Application shutdown", extra={"environment": settings.app_env})


app = FastAPI(
    title=settings.app_name,
    version=APP_VERSION,
    description="Lifetime and family health intelligence API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(ApiError, api_error_handler)
app.include_router(api_router)


@app.get("/", response_model=RootMetadata, tags=["metadata"])
async def root() -> RootMetadata:
    """Return non-sensitive metadata for the API root."""

    return RootMetadata(name=settings.app_name, environment=settings.app_env)

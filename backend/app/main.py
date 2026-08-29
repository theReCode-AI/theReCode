from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.init_db import shutdown_database
from app.db.mongodb import mongodb_manager
from app.google_adk.bootstrap import bootstrap_google_genai

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hook for startup and shutdown."""
    configure_logging(settings)
    bootstrap_google_genai(settings)
    logger.info(
        "Starting application",
        extra={
            "app_name": settings.app_name,
            "environment": settings.environment,
            "stage": "startup",
        },
    )
    # Do not block Cloud Run PORT bind on MongoDB — connect lazily on first request.
    try:
        yield
    finally:
        shutdown_database(mongodb_manager)
        logger.info("Application stopped", extra={"stage": "shutdown"})


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()

"""FastAPI application factory with lifespan management."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import batch, convert, events, health, jobs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown tasks for the FastAPI application.

    Args:
        app: FastAPI application instance

    Yields:
        Control during application lifetime
    """
    # Startup
    logger.info("Starting Gobbler API server")
    logger.info("Initializing services...")

    # TODO: Add service initialization here when daemon integration is ready
    # - Connect to Redis
    # - Initialize queue workers
    # - Setup event bus

    yield

    # Shutdown
    logger.info("Shutting down Gobbler API server")
    logger.info("Cleaning up resources...")

    # TODO: Add cleanup here when daemon integration is ready
    # - Close Redis connections
    # - Shutdown workers
    # - Cleanup temporary files


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Gobbler API",
        description=(
            "REST API for Gobbler - Universal Content Conversion Fabric. "
            "Convert YouTube videos, audio files, documents, and web pages to markdown."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS for browser access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Configure based on environment
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router)
    app.include_router(convert.router)
    app.include_router(batch.router)
    app.include_router(jobs.router)
    app.include_router(events.router)

    # Add exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Global exception handler for unhandled errors."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc),
            },
        )

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "gobbler_api.server:app",
        host="0.0.0.0",
        port=4600,
        reload=True,
        log_level="info",
    )

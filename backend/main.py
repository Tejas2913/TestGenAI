import structlog
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.v2.router import v2_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.session import dispose_engine, engine
from app.exceptions.handlers import register_exception_handlers
from app.middleware import RequestLoggingMiddleware

import app.models  # noqa: F401 — register models with Base.metadata

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle.

    Phase 3 additions:
      - startup_recovery(): marks crashed PROCESSING jobs as ORPHANED
        and re-queues eligible ones for retry.
      - schedule_recovery_jobs(): re-executes recovered jobs as background
        tasks now that the event loop is running.
    """
    logger.info(
        "application_starting",
        project=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT.value,
    )
    if settings.is_development:
        Base.metadata.create_all(bind=engine)
        logger.info("database_tables_created")

    # Phase 3: Recover jobs that were PROCESSING when the previous process crashed.
    try:
        from app.services.job_engine import schedule_recovery_jobs, startup_recovery
        requeued = startup_recovery()
        if requeued > 0:
            logger.info("startup_recovery_scheduling_jobs", count=requeued)
            await schedule_recovery_jobs()
    except Exception as exc:
        # Startup recovery failure must never prevent the application from
        # starting — log and continue.
        logger.error("startup_recovery_failed", error=str(exc), exc_info=True)

    yield

    dispose_engine()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging(settings.LOG_LEVEL)

    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    # V1 — frozen synchronous API (unchanged)
    application.include_router(api_router, prefix="/api/v1")

    # V2.1 — async job-based API (Phase 3: job endpoints active)
    application.include_router(v2_router, prefix="/api/v2")

    return application


app = create_app()

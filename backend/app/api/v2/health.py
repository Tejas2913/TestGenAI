"""V2 health endpoints: /live and /ready.

/live  — Liveness probe.
         Returns 200 immediately if the FastAPI event loop is responsive.
         Must NEVER perform any I/O — used by process supervisors to detect
         a completely hung process.

/ready — Readiness probe.
         Verifies the application can serve generation requests by checking
         that the database is reachable and required configuration is loaded.

         Deliberately does NOT call the Gemini API. An external LLM outage
         must not prevent the process from being marked ready, and must not
         consume API quota during health checks.

         Returns HTTP 200 when ready, HTTP 503 when not ready.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.session import check_database_connection
from app.schemas.health import LivenessResponse, ReadinessResponse

router = APIRouter(tags=["health-v2"])


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description=(
        "Returns 200 OK immediately if the FastAPI process is alive. "
        "Performs no I/O."
    ),
)
async def liveness() -> LivenessResponse:
    """Liveness check — confirms the event loop is running."""
    return LivenessResponse(status="alive")


@router.get(
    "/ready",
    summary="Readiness probe",
    description=(
        "Returns 200 OK when the application can serve requests. "
        "Checks database connectivity only — does NOT call the LLM."
    ),
)
async def readiness() -> JSONResponse:
    """Readiness check — verifies database connectivity and configuration.

    Returns:
        200 with ReadinessResponse when all checks pass.
        503 with ReadinessResponse (ready=False) when any check fails.
    """
    db_ok = check_database_connection()
    config_ok = bool(settings.DATABASE_URL)

    ready = db_ok and config_ok

    body = ReadinessResponse(
        ready=ready,
        database=db_ok,
        configuration=config_ok,
    )

    status_code = 200 if ready else 503
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
    )

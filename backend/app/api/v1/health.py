"""Health check endpoint with database and LLM provider verification."""

from fastapi import APIRouter

from app.core.config import settings
from app.db.session import check_database_connection
from app.schemas.health import HealthResponse

router = APIRouter()


def _check_llm_provider() -> bool:
    """Check whether the LLM provider is correctly configured.

    Verifies the API key is present and non-empty.
    Does NOT make a real API call (too expensive for health checks).
    """
    return bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health status including database and LLM readiness."""
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        architecture_version=settings.ARCHITECTURE_VERSION,
        environment=settings.ENVIRONMENT.value,
        database=check_database_connection(),
        llm_provider=_check_llm_provider(),
    )

"""Health check response schemas.

V1.0 frozen contract:
  HealthResponse — returned by /api/v1/health

V2.1 additions:
  LivenessResponse  — returned by /api/v2/live
  ReadinessResponse — returned by /api/v2/ready
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response from the V1 /health endpoint.

    V1.0 contract — additive only. Do not rename or remove fields.
    V2 may add optional fields (e.g. sandbox_ready, rag_ready).
    """

    status: str = Field(description="Service health status ('healthy')")
    version: str = Field(description="Application version (e.g. '1.0.0')")
    architecture_version: str = Field(description="Architecture version (e.g. '1.0')")
    environment: str = Field(description="Current runtime environment")
    database: bool = Field(description="Database connectivity status")
    llm_provider: bool = Field(description="LLM provider configuration status")


class LivenessResponse(BaseModel):
    """Response from the V2 /live endpoint.

    Returns immediately with no I/O. Status is always "alive"
    while the FastAPI process is running.
    """

    status: str = Field(
        default="alive",
        description="Liveness status — always 'alive' when the process responds",
    )


class ReadinessResponse(BaseModel):
    """Response from the V2 /ready endpoint.

    Indicates whether the application can currently serve requests.
    HTTP 200 when ready=True, HTTP 503 when ready=False.
    """

    ready: bool = Field(description="True when all checks pass and the app can serve requests")
    database: bool = Field(description="True when database connection is reachable")
    configuration: bool = Field(description="True when required configuration is present")

"""Generation API endpoints.

Thin route handlers that delegate entirely to GenerationService.
No business logic, no AI logic, no direct DB access.
"""

from fastapi import APIRouter, Depends, Query

from app.exceptions import NotFoundException
from app.schemas.common import PaginatedResponse
from app.schemas.generation import GenerationCreate, GenerationResponse
from app.services.generation_service import GenerationService
from dependencies import get_generation_service

router = APIRouter()


@router.post("/generate", response_model=GenerationResponse, status_code=201)
def create_generation(
    body: GenerationCreate,
    service: GenerationService = Depends(get_generation_service),
):
    """Submit source code for AI-powered test generation."""
    record = service.generate(
        source_code=body.source_code,
        specification=body.specification,
        language=body.language,
        framework=body.framework,
    )
    return record


@router.get("/generations/{generation_id}", response_model=GenerationResponse)
def get_generation(
    generation_id: str,
    service: GenerationService = Depends(get_generation_service),
):
    """Retrieve a single generation by its ID."""
    record = service.get_by_id(generation_id)
    if record is None:
        raise NotFoundException(detail=f"Generation '{generation_id}' not found")
    return record


@router.get("/generations", response_model=PaginatedResponse[GenerationResponse])
def list_generations(
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    service: GenerationService = Depends(get_generation_service),
):
    """List generation history with pagination."""
    items, total = service.get_history(page=page, size=size)
    return PaginatedResponse(
        items=[GenerationResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
    )

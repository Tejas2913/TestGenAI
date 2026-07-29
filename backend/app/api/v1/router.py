"""Versioned API router aggregating all v1 endpoints."""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.generations import router as generations_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(generations_router, tags=["generations"])

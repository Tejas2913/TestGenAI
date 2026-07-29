"""V2 API router — aggregates all V2 endpoint routers.

V2 endpoints are mounted under /api/v2 in main.py.

Phase 1: health endpoints (/live, /ready)
Phase 2: authentication endpoints (/auth/register, /auth/login, /auth/keys)
Phase 3: async job endpoints (/jobs/generate, /jobs/{job_id})
"""

from fastapi import APIRouter

from app.api.v2.auth import router as auth_router
from app.api.v2.health import router as health_router
from app.api.v2.jobs import router as jobs_router

v2_router = APIRouter()

# Health endpoints must remain public — liveness probes must never require auth.
v2_router.include_router(health_router)

# Auth endpoints handle their own per-route auth via Depends(require_active_user).
v2_router.include_router(auth_router)

# Job endpoints — require authentication (enforced per-route in jobs.py).
v2_router.include_router(jobs_router)

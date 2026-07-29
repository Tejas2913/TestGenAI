# TestGen AI v2.2 — Production Deployment Checklist

**Version**: 2.2.0  
**Release Target**: Production Deployment (`v2.2.0`)  

---

## 1. Pre-Deployment Verification

- [x] **Backend Test Suite**: Verify 100% pass rate on unit & integration tests (`pytest tests/v2/`).
- [x] **Frontend Production Build**: Verify Vite bundle compiles cleanly (`npm run build` in `frontend/`).
- [x] **Environment Variables**: Verify `.env` configuration template contains all required keys:
  - `GEMINI_API_KEY`
  - `JWT_SECRET_KEY`
  - `DATABASE_URL`
  - `ENABLE_QUALITY_EVALUATION=true`
  - `ENABLE_MUTATION_TESTING=true`
  - `ENABLE_SELF_HEAL=true`
  - `MAX_MUTANTS=20`
  - `EXECUTION_TIMEOUT=30`

---

## 2. Docker & Container Security Verification

- [x] **Multi-Stage Build**: Ensure Dockerfile uses multi-stage builds for optimized image sizes.
- [x] **Non-Root Execution**: Container process runs under non-privileged user (`appuser`).
- [x] **Sandbox Resource Limits**: Container limits enforced (`cpus: 1.0`, `memory: 256m`).
- [x] **Network Security**: Docker sandbox container runs with `--network none` during untrusted code execution.

---

## 3. Database Migration & Schema Setup

- [x] **Alembic Migrations**: Verify all database migration scripts are applied:
  - `alembic upgrade head`
- [x] **Index Health**: Verify indexes on `jobs(user_id, status)` and `generations(created_at)`.

---

## 4. API & Health Check Verification

- [x] **Health Check Endpoint**: `GET /api/v2/health` returns `200 OK` with database status `healthy`.
- [x] **RFC 7807 Exception Format**: Verify error responses output RFC 7807 Problem Details JSON format.
- [x] **CORS Configuration**: Verify allowed origins, headers, and credentials settings.

---

## 5. Post-Deployment Verification

- [x] **Submit Test Generation Job**: `POST /api/v2/jobs/generate` returns `202 Accepted` with `job_id`.
- [x] **Poll Job Diagnostics**: `GET /api/v2/jobs/{job_id}` returns status `completed` with embedded `quality_metrics`.
- [x] **React Dashboard Verification**: Verify UI loads Quality Cards, Pipeline Timeline, Coverage, and Mutant Details Table without rendering errors.

"""Dependency injection functions for FastAPI routes.

V1 dependencies (frozen):
  get_db                 — request-scoped DB session
  get_settings           — settings singleton
  get_generation_service — wired GenerationService for V1 routes

V2.1 additions (Phase 1):
  get_job_repository     — JobRepository for V2 async job engine
  get_user_repository    — UserRepository for V2 auth
  get_api_key_repository — ApiKeyRepository for V2 API key auth

V2.1 additions (Phase 2):
  get_sandbox_client     — SandboxClient for V2 execution pipeline

V2.1 additions (Phase 4):
  get_l1_cache           — Application-level L1Cache singleton
  get_cache_repository   — Request-scoped CacheRepository for L2
  get_cache_manager      — CacheManager wiring L1 + L2
  get_context_provider   — ContextProvider configured from settings
"""

from collections.abc import Generator

from app.ai.providers.gemini_provider import GeminiProvider
from app.cache.l1_cache import L1Cache
from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.cache_repository import CacheRepository
from app.repositories.generation_repository import GenerationRepository
from app.repositories.job_repository import JobRepository
from app.repositories.user_repository import UserRepository
from app.services.generation_service import GenerationService


def get_db() -> Generator:
    """Yield a database session scoped to the request lifecycle."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_settings() -> Settings:
    """Return the application settings singleton."""
    return settings


def get_generation_service() -> Generator[GenerationService, None, None]:
    """Construct a GenerationService with all dependencies.

    Creates a request-scoped DB session and wires the GeminiProvider,
    GenerationRepository, ContextProvider, and CacheManager (Phase 4)
    into the service.
    """
    db = SessionLocal()
    try:
        repository = GenerationRepository(db)
        provider = GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model_name=settings.GEMINI_MODEL,
            temperature=settings.GEMINI_TEMPERATURE,
            max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
            timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
            max_retries=settings.GEMINI_MAX_RETRIES,
        )

        # Phase 4: inject ContextProvider
        context_provider = get_context_provider()

        # Phase 4: inject CacheManager (with L2 repo bound to this session)
        cache_mgr = None
        if settings.ENABLE_L1_CACHE or settings.ENABLE_L2_CACHE:
            from app.cache.manager import CacheManager
            cache_repo = CacheRepository(db)
            cache_mgr = CacheManager(l1=_l1_cache_singleton, cache_repo=cache_repo)

        yield GenerationService(
            repository=repository,
            llm_provider=provider,
            context_provider=context_provider,
            cache_manager=cache_mgr,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# V2.1 repository dependencies — Phase 1
# ---------------------------------------------------------------------------


def get_job_repository() -> Generator[JobRepository, None, None]:
    """Yield a request-scoped JobRepository for V2 async job endpoints."""
    db = SessionLocal()
    try:
        yield JobRepository(db)
    finally:
        db.close()


def get_user_repository() -> Generator[UserRepository, None, None]:
    """Yield a request-scoped UserRepository.

    Phase 1 registers this dependency.
    Phase 2 auth enforcement consumes it.
    """
    db = SessionLocal()
    try:
        yield UserRepository(db)
    finally:
        db.close()


def get_api_key_repository() -> Generator[ApiKeyRepository, None, None]:
    """Yield a request-scoped ApiKeyRepository.

    Phase 1 registers this dependency.
    Phase 2 API key validation consumes it.
    """
    db = SessionLocal()
    try:
        yield ApiKeyRepository(db)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# V2.1 sandbox dependency — Phase 2
# ---------------------------------------------------------------------------

# Module-level singleton — SandboxClient is stateless and safe to share.
_sandbox_client_instance: "SandboxClient | None" = None


def get_sandbox_client() -> "SandboxClient":
    """Return the application-level SandboxClient singleton.

    Phase 2 prepares this dependency.
    Phase 3 injects it into the async generation pipeline via Depends().

    The client is a lightweight HTTP wrapper — it is safe to share
    across requests (all state is in the SandboxExecutor sidecar).
    """
    global _sandbox_client_instance
    if _sandbox_client_instance is None:
        from app.sandbox.client import SandboxClient
        _sandbox_client_instance = SandboxClient()
    return _sandbox_client_instance


# Type alias for the forward reference above
from app.sandbox.client import SandboxClient  # noqa: E402 — intentional late import


# ---------------------------------------------------------------------------
# V2.1 cache dependencies — Phase 4
# ---------------------------------------------------------------------------

# Application-level L1 cache singleton.
# Shared across all requests — the cache itself is thread-safe via RLock.
# Size and TTL are read from settings at first import.
_l1_cache_singleton = L1Cache(
    max_size=settings.L1_CACHE_MAX_SIZE,
    ttl_seconds=settings.L1_CACHE_TTL_SECONDS,
)


def get_l1_cache() -> L1Cache:
    """Return the application-level L1 in-memory cache singleton.

    The singleton is created once at import time using settings values.
    It is safe to call from multiple threads simultaneously.
    """
    return _l1_cache_singleton


def get_cache_repository() -> Generator[CacheRepository, None, None]:
    """Yield a request-scoped CacheRepository bound to a fresh DB session.

    Required by CacheManager for L2 reads and writes.
    """
    db = SessionLocal()
    try:
        yield CacheRepository(db)
    finally:
        db.close()


def get_cache_manager() -> Generator["CacheManager", None, None]:  # type: ignore[name-defined]
    """Yield a request-scoped CacheManager wiring L1 + L2.

    L1 is the application singleton. L2 repo is bound to a fresh DB session
    for this request. The manager is discarded after the request completes;
    the L1 singleton persists.
    """
    from app.cache.manager import CacheManager
    db = SessionLocal()
    try:
        cache_repo = CacheRepository(db)
        yield CacheManager(l1=_l1_cache_singleton, cache_repo=cache_repo)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# V2.1 context provider dependency — Phase 4
# ---------------------------------------------------------------------------


def get_context_provider():
    """Return the ContextProvider configured via settings.CONTEXT_PROVIDER_CLASS.

    Currently only "default" is supported (returns empty string).
    Future: "rag" will return a RAG-backed provider (Phase 5+).
    """
    from app.context.provider import get_context_provider as _factory
    return _factory()

"""FastAPI authentication dependencies — Phase 2.

Provides two DI callables for protected V2 endpoints:

  get_current_user
    Accepts Bearer JWT OR X-API-Key header.
    Returns the authenticated User ORM instance.
    Raises AuthException (401) if credentials are absent or invalid.

  require_active_user
    Wraps get_current_user and additionally checks is_active == True.
    Raises AuthException (403) for disabled accounts.

Architecture rule: V1 routes never consume these dependencies.
The ENABLE_AUTH flag gates enforcement so tests can disable it
without modifying route code.
"""

import hashlib

import jwt
import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_access_token
from app.core.config import settings
from app.db.session import SessionLocal
from app.exceptions import AuthException
from app.models.user import User
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.user_repository import UserRepository

logger = structlog.get_logger()

# HTTPBearer auto-parses "Authorization: Bearer <token>" headers.
# auto_error=False lets us fall through to X-API-Key checking.
_bearer_scheme = HTTPBearer(auto_error=False)


def _get_user_by_id(user_id: str) -> User | None:
    """Load a User record by primary key using a short-lived session."""
    db = SessionLocal()
    try:
        return UserRepository(db).get_by_id(user_id)
    finally:
        db.close()


def _get_user_by_api_key(raw_key: str) -> User | None:
    """Validate a raw API key and return the owning User, or None.

    Hashes the raw key with SHA-256, looks up the hash in api_keys,
    then returns the corresponding User.
    """
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db = SessionLocal()
    try:
        api_key_repo = ApiKeyRepository(db)
        api_key = api_key_repo.get_by_hash(key_hash)
        if api_key is None:
            return None
        return UserRepository(db).get_by_id(api_key.user_id)
    finally:
        db.close()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> User:
    """Authenticate the request via Bearer JWT or X-API-Key header.

    Auth is bypassed when ENABLE_AUTH=False (development/test mode).
    In that case a sentinel anonymous User object is returned.

    Priority:
      1. Authorization: Bearer <JWT>
      2. X-API-Key: <raw_key>
      3. Raise 401

    Returns:
        The authenticated User ORM instance.

    Raises:
        AuthException: 401 when credentials are missing or invalid.
    """
    # ----------------------------------------------------------------
    # Development bypass — NEVER enabled in production
    # ----------------------------------------------------------------
    if not settings.ENABLE_AUTH:
        logger.debug("auth_bypass_enabled", path=request.url.path)
        # Return a lightweight sentinel — enough for Phase 2 tests
        anon = User()
        anon.id = "anonymous"
        anon.email = "anonymous@dev.local"
        anon.is_active = True
        return anon

    # ----------------------------------------------------------------
    # 1. Bearer JWT
    # ----------------------------------------------------------------
    if credentials is not None:
        token = credentials.credentials
        try:
            payload = decode_access_token(token)
            user_id: str = payload["sub"]
        except jwt.ExpiredSignatureError:
            logger.warning("jwt_expired", path=request.url.path)
            raise AuthException("Access token has expired")
        except jwt.PyJWTError as exc:
            logger.warning("jwt_invalid", error=str(exc), path=request.url.path)
            raise AuthException("Invalid access token")

        user = _get_user_by_id(user_id)
        if user is None:
            raise AuthException("User not found")
        logger.debug("jwt_auth_success", user_id=user_id)
        return user

    # ----------------------------------------------------------------
    # 2. X-API-Key header
    # ----------------------------------------------------------------
    raw_key = request.headers.get("X-API-Key")
    if raw_key:
        user = _get_user_by_api_key(raw_key)
        if user is None:
            logger.warning("api_key_invalid", path=request.url.path)
            raise AuthException("Invalid or revoked API key")
        logger.debug("api_key_auth_success", user_id=user.id)
        return user

    # ----------------------------------------------------------------
    # 3. No credentials
    # ----------------------------------------------------------------
    logger.warning("auth_missing_credentials", path=request.url.path)
    raise AuthException("Authentication required")


def require_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Extend get_current_user to reject disabled accounts.

    Returns:
        The authenticated and active User.

    Raises:
        AuthException: 403 when the account is disabled.
    """
    if not user.is_active:
        # AuthException defaults to 401; we need 403 for a disabled account.
        # Raise AppException directly to avoid the subclass default.
        from app.exceptions import AppException
        raise AppException(
            detail="Account is disabled",
            error_code="AUTH_ERROR",
            status_code=403,
        )
    return user

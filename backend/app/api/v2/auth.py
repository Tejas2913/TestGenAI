"""V2 Authentication endpoints — Phase 2.

Routes:
  POST   /api/v2/auth/register        — create a new user account
  POST   /api/v2/auth/login           — obtain a JWT access token
  POST   /api/v2/auth/keys            — create a new API key
  GET    /api/v2/auth/keys            — list all active API keys for the caller
  DELETE /api/v2/auth/keys/{key_id}   — revoke an API key

V1 routes are not touched. All auth logic is in app/auth/.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends

from app.auth.dependencies import require_active_user
from app.auth.jwt import create_access_token
from app.auth.password import hash_password, verify_password
from app.core.config import settings
from app.exceptions import AuthException, NotFoundException, ValidationException
from app.models.user import User
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    ApiKeyCreatedResponse,
    ApiKeyListItem,
    ApiKeyListResponse,
    CreateApiKeyRequest,
    LoginRequest,
    RegisterRequest,
    RevokeApiKeyResponse,
    TokenResponse,
    UserResponse,
)
from dependencies import get_api_key_repository, get_user_repository

router = APIRouter(prefix="/auth", tags=["auth-v2"])
logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Register a new user account",
)
def register(
    body: RegisterRequest,
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserResponse:
    """Create a new user account.

    - Email must be unique.
    - Password is hashed with Argon2id before storage.
    - Returns the new user record (no credentials included).
    """
    # Check uniqueness before hashing (saves compute on obvious duplicates)
    existing = user_repo.get_by_email(body.email)
    if existing is not None:
        raise ValidationException(f"Email '{body.email}' is already registered")

    hashed = hash_password(body.password)
    user_id = str(uuid.uuid4())

    user = user_repo.create(
        {
            "id": user_id,
            "email": body.email,
            "display_name": body.display_name,
            "hashed_password": hashed,
            "is_active": True,
        }
    )
    logger.info("user_registered", user_id=user_id, email=body.email)
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Obtain a JWT access token",
)
def login(
    body: LoginRequest,
    user_repo: UserRepository = Depends(get_user_repository),
) -> TokenResponse:
    """Authenticate with email + password, returning a 24-hour JWT.

    Uses constant-time comparison to prevent timing attacks.
    Returns 401 for both 'user not found' and 'wrong password'
    to avoid email enumeration.
    """
    user = user_repo.get_by_email(body.email)

    # Always run verify_password to maintain constant-time behaviour
    # even when the user does not exist.
    dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$fakesaltfakesalt$fakehashfakehashfakehashfakehashfakehashfakeha"
    stored_hash = user.hashed_password if user and user.hashed_password else dummy_hash
    password_valid = verify_password(body.password, stored_hash)

    if user is None or not password_valid:
        logger.warning("login_failed", email=body.email)
        raise AuthException("Invalid email or password")

    if not user.is_active:
        raise AuthException("Account is disabled")

    token = create_access_token(user.id)
    expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600

    logger.info("login_success", user_id=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=expires_in,
    )


# ---------------------------------------------------------------------------
# API Key management
# ---------------------------------------------------------------------------


@router.post(
    "/keys",
    response_model=ApiKeyCreatedResponse,
    status_code=201,
    summary="Create a new API key",
)
def create_api_key(
    body: CreateApiKeyRequest,
    current_user: User = Depends(require_active_user),
    api_key_repo: ApiKeyRepository = Depends(get_api_key_repository),
) -> ApiKeyCreatedResponse:
    """Generate and store a new API key for the current user.

    The raw key is returned ONCE in this response. It is never stored
    in the database — only its SHA-256 hash is persisted. The caller
    must save the raw key immediately.
    """
    # Generate a cryptographically secure random 32-byte key,
    # base64url-encoded for safe transport (no padding).
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_id = str(uuid.uuid4())

    api_key = api_key_repo.create(
        {
            "id": key_id,
            "user_id": current_user.id,
            "key_hash": key_hash,
            "label": body.label,
        }
    )
    logger.info("api_key_created", user_id=current_user.id, key_id=key_id)

    return ApiKeyCreatedResponse(
        id=api_key.id,
        raw_key=raw_key,
        label=api_key.label,
        created_at=api_key.created_at,
    )


@router.get(
    "/keys",
    response_model=ApiKeyListResponse,
    summary="List all active API keys for the current user",
)
def list_api_keys(
    current_user: User = Depends(require_active_user),
    api_key_repo: ApiKeyRepository = Depends(get_api_key_repository),
) -> ApiKeyListResponse:
    """Return all active (non-revoked) API keys owned by the current user."""
    keys = api_key_repo.get_keys_for_user(current_user.id)
    return ApiKeyListResponse(
        keys=[ApiKeyListItem.model_validate(k) for k in keys]
    )


@router.delete(
    "/keys/{key_id}",
    response_model=RevokeApiKeyResponse,
    summary="Revoke an API key",
)
def revoke_api_key(
    key_id: str,
    current_user: User = Depends(require_active_user),
    api_key_repo: ApiKeyRepository = Depends(get_api_key_repository),
) -> RevokeApiKeyResponse:
    """Revoke an API key by setting revoked_at to the current UTC timestamp.

    The key is NOT deleted — the revocation record is preserved for auditing.
    Only the owner of the key can revoke it.
    """
    key = api_key_repo.get_by_id(key_id)
    if key is None or key.user_id != current_user.id:
        raise NotFoundException(f"API key '{key_id}' not found")

    if key.revoked_at is not None:
        raise ValidationException("API key is already revoked")

    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    api_key_repo.update(key_id, {"revoked_at": now})

    logger.info("api_key_revoked", user_id=current_user.id, key_id=key_id)
    return RevokeApiKeyResponse(id=key_id, revoked=True)

"""JWT access token encoding and decoding — Phase 2.

Uses PyJWT (HS256) to create and verify 24-hour access tokens.
No refresh tokens — intentional V2.1 simplification per architecture.

Token payload structure:
  sub  — user ID (UUID string)
  type — "access" (guards against using other token types)
  exp  — expiry timestamp (UTC epoch seconds)
  iat  — issued-at timestamp (UTC epoch seconds)
"""

from datetime import datetime, timedelta, timezone

import jwt
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# The JWT type claim prevents accidentally accepting e.g. a future
# password-reset token where an access token is expected.
_TOKEN_TYPE = "access"


def create_access_token(user_id: str) -> str:
    """Encode a signed JWT access token for the given user.

    Args:
        user_id: The UUID string primary key of the authenticated user.

    Returns:
        Signed JWT string. Clients must send this as:
        ``Authorization: Bearer <token>``
    """
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS)

    payload: dict = {
        "sub": user_id,
        "type": _TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    logger.debug("jwt_token_created", user_id=user_id)
    return token


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token.

    Verifies the signature, expiry, and ``type`` claim.

    Args:
        token: The raw JWT string from the Authorization header.

    Returns:
        The decoded payload dict, containing at minimum ``sub`` (user_id).

    Raises:
        jwt.ExpiredSignatureError: When the token has expired.
        jwt.InvalidTokenError:     When the token is invalid for any other reason.
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )

    # Guard against using non-access tokens (e.g. future password-reset tokens).
    if payload.get("type") != _TOKEN_TYPE:
        raise jwt.InvalidTokenError("Token type mismatch")

    return payload


def extract_user_id(token: str) -> str | None:
    """Extract user_id from a token without raising on validation failure.

    Convenience wrapper for situations where a missing or invalid token
    should produce None rather than an exception (e.g. optional auth).

    Returns:
        user_id string on success, None on any failure.
    """
    try:
        payload = decode_access_token(token)
        return payload.get("sub")
    except jwt.PyJWTError:
        return None

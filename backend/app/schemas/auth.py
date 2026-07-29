"""Pydantic schemas for V2 authentication endpoints — Phase 2.

Schemas defined here are the request/response contracts for:
  POST /api/v2/auth/register
  POST /api/v2/auth/login
  POST /api/v2/auth/keys
  GET  /api/v2/auth/keys
  DELETE /api/v2/auth/keys/{key_id}

These schemas are additive and must NOT modify V1 contracts.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr = Field(description="User email address (must be unique)")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password (minimum 8 characters)",
    )
    display_name: str | None = Field(
        default=None,
        max_length=200,
        description="Optional display name",
    )


class UserResponse(BaseModel):
    """Response representing a registered user.

    Never includes the hashed_password or any credential material.
    """

    id: str
    email: str
    display_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Request body for login (email + password)."""

    email: EmailStr = Field(description="Registered email address")
    password: str = Field(description="Account password")


class TokenResponse(BaseModel):
    """Response from a successful login.

    Contains only the access token — no refresh token per architecture.
    """

    access_token: str = Field(description="Signed JWT access token")
    token_type: str = Field(default="bearer", description="Always 'bearer'")
    expires_in_seconds: int = Field(
        description="Token lifetime in seconds (24 hours = 86400)"
    )


# ---------------------------------------------------------------------------
# API Key management
# ---------------------------------------------------------------------------


class CreateApiKeyRequest(BaseModel):
    """Request body for creating a new API key."""

    label: str | None = Field(
        default=None,
        max_length=200,
        description="Human-readable label (e.g. 'CI pipeline key')",
    )


class ApiKeyCreatedResponse(BaseModel):
    """Response after creating a new API key.

    The raw_key is returned ONCE. It is never stored and cannot be retrieved.
    The caller must save it securely.
    """

    id: str = Field(description="API key record ID")
    raw_key: str = Field(
        description="The raw API key — shown ONCE, store it securely"
    )
    label: str | None = Field(description="Human-readable label")
    created_at: datetime = Field(description="Creation timestamp")


class ApiKeyListItem(BaseModel):
    """A single API key entry in the list response.

    raw_key is NOT included — it was only available at creation time.
    """

    id: str
    label: str | None
    created_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyListResponse(BaseModel):
    """Response for listing all API keys owned by the current user."""

    keys: list[ApiKeyListItem]


class RevokeApiKeyResponse(BaseModel):
    """Response after revoking an API key."""

    id: str = Field(description="Revoked key ID")
    revoked: bool = Field(default=True)

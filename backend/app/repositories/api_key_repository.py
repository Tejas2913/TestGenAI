"""Repository for ApiKey model — V2.1.

Provides CRUD operations from BaseRepository plus a lookup-by-hash
method needed for API key validation in Phase 2.
"""

from sqlalchemy import select

from app.models.api_key import ApiKey
from app.repositories.base import BaseRepository


class ApiKeyRepository(BaseRepository[ApiKey]):
    """Data access layer for ApiKey records.

    Inherits standard create / get_by_id / update / get_all.
    Phase 2 will use get_by_hash during request authentication.
    """

    model = ApiKey

    def get_by_hash(self, key_hash: str) -> ApiKey | None:
        """Return the ApiKey record with the given SHA-256 hash, or None.

        Only returns non-revoked keys (revoked_at IS NULL).
        """
        return self._session.scalar(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.revoked_at.is_(None),
            )
        )

    def get_keys_for_user(self, user_id: str) -> list[ApiKey]:
        """Return all active API keys for a given user."""
        return list(
            self._session.scalars(
                select(ApiKey).where(
                    ApiKey.user_id == user_id,
                    ApiKey.revoked_at.is_(None),
                )
            )
        )

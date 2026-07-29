"""Repository for User model — V2.1.

Provides CRUD operations from BaseRepository plus a lookup-by-email
method needed by authentication in Phase 2.
"""

from sqlalchemy import select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Data access layer for User records.

    Inherits standard create / get_by_id / update / get_all.
    Phase 2 adds password hashing and JWT issuance on top of this layer.
    """

    model = User

    def get_by_email(self, email: str) -> User | None:
        """Return the user with the given email address, or None."""
        return self._session.scalar(
            select(User).where(User.email == email)
        )

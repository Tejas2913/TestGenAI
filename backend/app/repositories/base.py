"""Generic base repository with foundational CRUD operations."""

from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """Provides type-safe CRUD operations for any ORM model.

    Subclass and set `model` to the concrete ORM class.
    """

    model: type[T]

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, data: dict) -> T:
        """Insert a new record and return the persisted instance."""
        instance = self.model(**data)
        self._session.add(instance)
        self._session.commit()
        self._session.refresh(instance)
        return instance

    def get_by_id(self, record_id: str) -> T | None:
        """Retrieve a single record by its primary key."""
        self._session.expire_all()
        return self._session.get(self.model, record_id)

    def update(self, record_id: str, data: dict) -> T | None:
        """Update specific fields on an existing record.

        Returns the updated instance, or None if not found.
        """
        instance = self.get_by_id(record_id)
        if instance is None:
            return None
        for key, value in data.items():
            setattr(instance, key, value)
        self._session.commit()
        self._session.refresh(instance)
        return instance

    def get_all(self, offset: int = 0, limit: int = 20) -> tuple[list[T], int]:
        """Return a paginated list of records and the total count.

        Results are ordered by created_at descending (newest first).
        """
        total = self._session.scalar(
            select(func.count()).select_from(self.model)
        )
        items = list(
            self._session.scalars(
                select(self.model)
                .order_by(self.model.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return items, total or 0

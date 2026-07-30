"""TestGen AI v2.3 — Base Context Indexer Framework

Abstract Base Class defining repository AST indexing APIs.
"""

from abc import ABC, abstractmethod
from typing import Optional
import structlog

from app.domain.v23_models import RepositoryContext

logger = structlog.get_logger()


class BaseContextIndexer(ABC):
    """Abstract base class for repository AST indexers."""

    def __init__(self, indexer_name: str) -> None:
        self.indexer_name = indexer_name
        self.logger = logger.bind(indexer=indexer_name)

    @abstractmethod
    def build_context(self, source_code: str, file_path: Optional[str] = None) -> RepositoryContext:
        """Parse source code AST and return a RepositoryContext object.

        Args:
            source_code: Python source code string.
            file_path: Optional relative file path in project workspace.

        Returns:
            RepositoryContext object.
        """
        pass

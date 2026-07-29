"""TestGen AI v2.3 — RepositoryContext Serializer

Deterministic text/markdown serialization of RepositoryContext domain objects.
Provides configurable truncation caps for LLM prompt token budgeting.
"""

from typing import Any, Dict, Optional
import structlog

from app.domain.v23_models import RepositoryContext

logger = structlog.get_logger()


class RepositoryContextSerializer:
    """Deterministic serializer for RepositoryContext objects."""

    def __init__(self, default_max_chars: int = 4000) -> None:
        self.default_max_chars = default_max_chars
        self.logger = logger.bind(component="RepositoryContextSerializer")

    def serialize(self, context: RepositoryContext, max_chars: Optional[int] = None) -> str:
        """Serialize RepositoryContext into structured Markdown text.

        Args:
            context: Populated RepositoryContext domain object.
            max_chars: Optional maximum character truncation limit.

        Returns:
            Serialized Markdown text representation.
        """
        limit = max_chars if max_chars is not None else self.default_max_chars
        lines = []

        lines.append("## Repository Context Summary")
        if context.metadata:
            root = context.metadata.get("root_path", "unknown")
            files_count = context.metadata.get("source_files_count", 0)
            lines.append(f"- **Root Path**: `{root}`")
            lines.append(f"- **Source Files**: {files_count}")

        if context.frameworks:
            fw_str = ", ".join(f"{k} (conf: {v})" for k, v in context.frameworks.items())
            lines.append(f"- **Detected Frameworks**: {fw_str}")

        if context.dependencies:
            deps_str = ", ".join(context.dependencies[:15])
            lines.append(f"- **Dependencies**: {deps_str}")

        if context.classes:
            lines.append("\n### Classes Identified")
            for cls_info in context.classes[:10]:
                name = cls_info.get("name", "Unknown")
                bases = ", ".join(cls_info.get("bases", []))
                base_str = f"({bases})" if bases else ""
                lines.append(f"- `class {name}{base_str}`")

        if context.functions:
            lines.append("\n### Key Functions")
            for func_info in context.functions[:15]:
                name = func_info.get("name", "unknown")
                args = ", ".join(func_info.get("args", []))
                async_prefix = "async " if func_info.get("is_async") else ""
                lines.append(f"- `{async_prefix}def {name}({args})`")

        if context.pytest_fixtures:
            fix_str = ", ".join(context.pytest_fixtures[:10])
            lines.append(f"\n- **Pytest Fixtures**: {fix_str}")

        if context.existing_tests:
            lines.append(f"\n- **Existing Test Files**: {len(context.existing_tests)}")

        result = "\n".join(lines)
        if len(result) > limit:
            result = result[: limit - 30] + "\n... [Context Truncated]"

        self.logger.debug("context_serialized", length=len(result), limit=limit)
        return result

"""ContextProvider abstraction — Phase 4.

Architecture purpose:
  The ContextProvider decouples GenerationService from the specifics of
  HOW additional context is gathered (local rules, repository analysis,
  RAG retrieval, etc.).

  GenerationService calls context_provider.get_context(source_code, specification)
  and uses the returned string to enrich the generation prompt WITHOUT knowing
  the source of that context.

Design:
  - Interface-based (ABC) so GenerationService depends only on the abstraction.
  - DefaultContextProvider returns an empty string (no-op) — fully backward
    compatible with all Phase 1/2/3 behaviour.
  - Future RAG-backed provider can be dropped in as a Phase 5 extension
    WITHOUT changing GenerationService.

DO NOT implement:
  - RAG retrieval
  - Vector database lookups
  - Embedding computation

These are Phase 5+ concerns. This module ONLY provides the abstraction.

Usage:
    # V1 / Phase 3 job engine — use default (no context)
    provider = DefaultContextProvider()
    context = provider.get_context(source_code, specification)  # ""

    # Future RAG provider (Phase 5)
    provider = RagContextProvider(vector_store=...)
    context = provider.get_context(source_code, specification)  # enriched

    # Inject into GenerationService
    service = GenerationService(
        repository=repo,
        llm_provider=llm,
        context_provider=provider,   # <- only abstraction used
    )
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ContextProvider(ABC):
    """Abstract interface for providing additional context during test generation.

    Implementors return a string that is injected into the generation prompt
    alongside the source code and optional specification. Returning an empty
    string is valid and means "no additional context."

    GenerationService depends ONLY on this interface, making it possible to
    swap implementations (default → RAG → custom) without modifying the service.
    """

    @abstractmethod
    def get_context(
        self,
        source_code: str,
        specification: str | None,
    ) -> str:
        """Return additional context to inject into the generation prompt.

        Args:
            source_code:   The raw source code for which tests are generated.
            specification: Optional natural-language test specification.

        Returns:
            A non-None string. Empty string means no additional context.
        """

    @property
    def provider_name(self) -> str:
        """Human-readable name for logging and observability."""
        return self.__class__.__name__


class DefaultContextProvider(ContextProvider):
    """Default implementation — returns empty string (no additional context).

    This is the backward-compatible implementation used in all Phase 1–3
    execution paths. Injecting this provider has zero effect on the
    generation prompt.

    The existence of this class as the default makes the Phase 5 RAG
    upgrade a simple dependency-injection change with no service rewrites.
    """

    def get_context(
        self,
        source_code: str,
        specification: str | None,
    ) -> str:
        """Return empty string — no additional context is injected."""
        return ""

    @property
    def provider_name(self) -> str:
        return "default"


def get_context_provider() -> ContextProvider:
    """Factory function that returns the configured ContextProvider.

    Reads settings.CONTEXT_PROVIDER_CLASS and returns the appropriate
    implementation. Currently only "default" is supported.

    Future values: "rag" will return a RAG-backed provider (Phase 5+).

    Returns:
        A ContextProvider instance.
    """
    from app.core.config import settings

    if settings.CONTEXT_PROVIDER_CLASS == "default":
        return DefaultContextProvider()

    # Safety net — fall back to default for unknown values
    return DefaultContextProvider()

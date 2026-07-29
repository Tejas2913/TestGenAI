"""Feature flag infrastructure for TestGen AI.

All V2 feature flags are defined in settings (app/core/config.py) and
default to False. This module provides a clean, centralized API for
checking flags so V2 code never reads settings directly.

Usage
-----
From a FastAPI endpoint or service:

    from app.core.feature_flags import feature_flags, require_feature

    # Soft check (returns bool)
    if feature_flags.sandbox:
        ...

    # Hard guard (raises HTTP 501 if disabled)
    require_feature(feature_flags.sandbox, "ENABLE_SANDBOX")

Design principles
-----------------
- V1 code does NOT call any of these helpers — they are inert in V1.
- V2 endpoints must call require_feature() as their first line.
- FeatureFlags is a thin read-only view of settings — no own state.
- All flag names mirror settings ENABLE_* names for grep-ability.
"""

from dataclasses import dataclass

from fastapi import HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class FeatureFlags:
    """Read-only snapshot of the current feature flag state.

    Properties mirror settings.ENABLE_* 1-to-1 for discoverability.
    Constructed once at module load; safe to use anywhere without
    importing settings directly.
    """

    sandbox: bool
    rag: bool
    self_heal: bool
    review: bool
    confidence: bool
    multi_provider: bool
    explainability: bool

    @classmethod
    def from_settings(cls) -> "FeatureFlags":
        """Build a FeatureFlags snapshot from current settings."""
        return cls(
            sandbox=settings.ENABLE_SANDBOX,
            rag=settings.ENABLE_RAG,
            self_heal=settings.ENABLE_SELF_HEAL,
            review=settings.ENABLE_REVIEW,
            confidence=settings.ENABLE_CONFIDENCE,
            multi_provider=settings.ENABLE_MULTI_PROVIDER,
            explainability=settings.ENABLE_EXPLAINABILITY,
        )

    def is_enabled(self, flag_name: str) -> bool:
        """Check a flag by its settings name (e.g. 'ENABLE_SANDBOX').

        Useful for dynamic checks when the flag name is a string.
        Raises AttributeError if the flag name is unknown.
        """
        # Strip the ENABLE_ prefix if present
        attr = flag_name.removeprefix("ENABLE_").lower()
        return getattr(self, attr)


# ---------------------------------------------------------------------------
# Module-level singleton — import and use this directly.
# ---------------------------------------------------------------------------
feature_flags: FeatureFlags = FeatureFlags.from_settings()


def require_feature(enabled: bool, flag_name: str) -> None:
    """Raise HTTP 501 if a feature flag is disabled.

    Call this as the first statement in any V2 endpoint or service method
    that is gated behind a feature flag.

    Args:
        enabled:   The flag value (e.g. feature_flags.sandbox)
        flag_name: Human-readable name for the error message (e.g. "ENABLE_SANDBOX")

    Raises:
        HTTPException(501): If the feature is not enabled.

    Example::

        @router.post("/sandbox/run")
        async def run_in_sandbox(...):
            require_feature(feature_flags.sandbox, "ENABLE_SANDBOX")
            ...
    """
    if not enabled:
        raise HTTPException(
            status_code=501,
            detail=(
                f"Feature '{flag_name}' is not enabled in this deployment. "
                "Contact your administrator to enable it."
            ),
        )

"""Cache key computation — Phase 4.

Architecture specification:
  Cache key  = SHA-256 of (source_code | specification | language | framework | prompt_version)
  Prompt hash = SHA-256 of the prompt version string (identifies template version)

All keys are 64-character hex strings (SHA-256 output).

The cache key uniquely identifies a specific generation REQUEST.
The prompt hash identifies the TEMPLATE that was active, allowing
the cache to be invalidated selectively when templates change.
"""

import hashlib


def compute_cache_key(
    source_code: str,
    specification: str | None,
    language: str,
    framework: str,
    prompt_version: str,
) -> str:
    """Compute a deterministic 64-char hex cache key for a generation request.

    The key is a SHA-256 hash of the five request fingerprint components
    joined by the pipe character (|). Each component is treated as a literal
    string — no normalisation is applied. This ensures identical inputs always
    produce identical keys, and any change to any component produces a
    different key.

    Args:
        source_code:    Raw source code to generate tests for.
        specification:  Optional natural-language test specification.
        language:       Programming language (e.g. "python").
        framework:      Test framework (e.g. "pytest").
        prompt_version: Active prompt template version (e.g. "v1").

    Returns:
        64-character lowercase hex string.
    """
    fingerprint = "|".join([
        source_code,
        specification or "",
        language,
        framework,
        prompt_version,
    ])
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def compute_prompt_hash(prompt_version: str) -> str:
    """Compute a stable hash of the active prompt template version.

    Used to tag L2 cache entries so that when templates are updated
    (prompt_version changes), old entries can be identified and purged.

    Args:
        prompt_version: The prompt version string (e.g. "v1", "v2").

    Returns:
        64-character lowercase hex string.
    """
    return hashlib.sha256(prompt_version.encode("utf-8")).hexdigest()

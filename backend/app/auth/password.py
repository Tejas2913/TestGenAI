"""Argon2 password hashing — Phase 2.

Uses argon2-cffi with the default PasswordHasher parameters which
follow the OWASP recommendation for Argon2id:
  - time_cost=3 (iterations)
  - memory_cost=65536 (64 MB)
  - parallelism=4

IMPORTANT: Raw passwords are NEVER stored, logged, or returned.
Only the opaque hash string is persisted in the User.hashed_password column.
"""

import structlog
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

logger = structlog.get_logger()

# Singleton hasher — constructed once, thread-safe for concurrent use.
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain_password: str) -> str:
    """Return an Argon2id hash of *plain_password*.

    The returned string includes the algorithm, parameters, salt, and hash
    in the standard PHC format and can be stored directly in the database.

    Args:
        plain_password: The raw password from the user registration form.

    Returns:
        Opaque Argon2id hash string safe for database storage.
    """
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify *plain_password* against the stored *hashed_password*.

    Returns True only when the password matches. Returns False for any
    mismatch or invalid-hash condition, avoiding information leakage.

    This function intentionally does NOT raise — callers should treat
    a False return as "credentials invalid" without inspecting the reason.

    Args:
        plain_password: The raw password from the login form.
        hashed_password: The Argon2id hash stored in the database.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return _hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except (VerificationError, InvalidHashError) as exc:
        logger.warning("password_verification_error", error=str(exc))
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Return True if the hash was produced with outdated parameters.

    Use this to silently upgrade hashes on successful login without
    forcing all users to reset their passwords.

    Args:
        hashed_password: The Argon2id hash stored in the database.

    Returns:
        True if the hash should be recomputed with current parameters.
    """
    return _hasher.check_needs_rehash(hashed_password)

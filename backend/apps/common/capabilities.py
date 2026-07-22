"""Helpers for issuing and verifying high-entropy management capabilities."""

import hashlib
import secrets

MANAGEMENT_TOKEN_BYTES = 32
_EMPTY_TOKEN_HASH = "0" * (hashlib.sha256().digest_size * 2)


def generate_management_token() -> str:
    """Return a URL-safe token backed by 256 bits of cryptographic randomness."""
    return secrets.token_urlsafe(MANAGEMENT_TOKEN_BYTES)


def hash_management_token(token: str) -> str:
    """Return the stable SHA-256 digest stored for a management token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def management_token_matches(candidate: str, stored_hash: str) -> bool:
    """Compare a candidate capability with a stored digest in constant time."""
    expected_hash = stored_hash if len(stored_hash) == len(_EMPTY_TOKEN_HASH) else _EMPTY_TOKEN_HASH
    matches = secrets.compare_digest(hash_management_token(candidate), expected_hash)
    return matches and bool(stored_hash)

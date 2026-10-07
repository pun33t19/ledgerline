"""Fingerprints of arguments and results that don't reveal them (ADR-008).

A plain SHA-256 of short arguments can be reversed by guessing: hash every
4-digit PIN and compare. An HMAC with a secret key can't be checked without
the key, yet whoever holds the key can still prove "these were the arguments".
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any

from ledgerline.pin.canonical import NotCanonicalizable, canonical_bytes

DEFAULT_KEY_FILE = Path.home() / ".ledgerline" / "digest.key"
KEY_BYTES = 32


class Digester:
    def __init__(self, key: bytes) -> None:
        if len(key) < 16:
            raise ValueError("digest key must be at least 16 bytes")
        self._key = key

    @classmethod
    def random(cls) -> Digester:
        return cls(secrets.token_bytes(KEY_BYTES))

    @classmethod
    def from_file(cls, path: Path = DEFAULT_KEY_FILE) -> Digester:
        """Load the tenant key, creating it (readable only by you) on first use."""
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(secrets.token_bytes(KEY_BYTES))
        return cls(path.read_bytes())

    def digest(self, value: Any) -> str:
        """HMAC-SHA256 over the RFC 8785 form of ``value``, as 64 hex characters."""
        try:
            data = canonical_bytes(value)
        except NotCanonicalizable:
            # e.g. an integer too large for JSON's safe range: still fingerprint it, deterministically
            data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        return hmac.new(self._key, data, hashlib.sha256).hexdigest()

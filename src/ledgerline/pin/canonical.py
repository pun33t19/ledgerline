"""Fingerprints that every implementation computes the same way.

``json.dumps`` output depends on settings (key order, spacing, number and
escape formatting), so two programs can serialise the same data differently.
RFC 8785, the JSON Canonicalization Scheme (JCS), fixes every one of those
choices, so the same tool definition always yields the same bytes, and the
same SHA-256, in any language. (ADR-003)
"""

from __future__ import annotations

import hashlib
from typing import Any

import rfc8785


class NotCanonicalizable(ValueError):
    """The value can't be canonicalised, e.g. an integer beyond JSON's safe range."""


def canonical_bytes(value: Any) -> bytes:
    try:
        data: bytes = rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, TypeError, ValueError) as e:
        raise NotCanonicalizable(str(e)) from e
    return data


def sha256_hex(value: Any) -> str:
    """SHA-256 of the RFC 8785 canonical form, as 64 hex characters."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

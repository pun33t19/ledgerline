from pathlib import Path

import pytest

from ledgerline.ledger.digest import Digester


def test_digest_is_keyed_and_canonical() -> None:
    a, b = Digester(b"k" * 32), Digester(b"x" * 32)
    args = {"location": "Pune", "unit": "celsius"}
    assert a.digest(args) == a.digest({"unit": "celsius", "location": "Pune"})  # key order irrelevant
    assert a.digest(args) != b.digest(args)  # without the key you can't recompute it
    assert a.digest(args) != a.digest({**args, "unit": "fahrenheit"})
    assert len(a.digest(args)) == 64


def test_huge_integers_still_get_a_digest() -> None:
    d = Digester(b"k" * 32)
    assert d.digest({"n": 2**80}) == d.digest({"n": 2**80})


def test_key_file_is_created_private_and_reused(tmp_path: Path) -> None:
    path = tmp_path / "keys" / "digest.key"
    first = Digester.from_file(path)
    assert path.stat().st_mode & 0o777 == 0o600
    assert Digester.from_file(path).digest({"a": 1}) == first.digest({"a": 1})


def test_short_keys_are_refused() -> None:
    with pytest.raises(ValueError, match="at least 16 bytes"):
        Digester(b"short")

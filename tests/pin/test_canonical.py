import pytest

from ledgerline.pin.canonical import NotCanonicalizable, canonical_bytes, sha256_hex


def test_rfc8785_number_and_key_rules() -> None:
    # The numbers example from RFC 8785 §3.2.2.3, plus key sorting.
    value = {"numbers": [333333333.33333329, 1e30, 4.50, 2e-3, 0.000000000000000000000000001], "a": 1}
    assert canonical_bytes(value) == b'{"a":1,"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27]}'


def test_hash_ignores_key_order_and_whitespace() -> None:
    assert sha256_hex({"name": "t", "description": "d"}) == sha256_hex({"description": "d", "name": "t"})


def test_hash_changes_with_any_character() -> None:
    assert sha256_hex({"description": "Get a fact."}) != sha256_hex({"description": "Get a fact!"})


def test_unsafe_integers_are_refused() -> None:
    with pytest.raises(NotCanonicalizable):
        sha256_hex({"n": 2**60})

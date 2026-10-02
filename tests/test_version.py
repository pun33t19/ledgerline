import re

import ledgerline


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", ledgerline.__version__)

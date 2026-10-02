import json
from pathlib import Path

import pytest

from ledgerline.pin.lockfile import Lockfile, LockfileError, PinnedTool

TOOL = {"name": "get_weather", "description": "Get the weather", "inputSchema": {"type": "object"}}


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "ledgerline.lock"
    Lockfile(tools={"get_weather": PinnedTool.of(TOOL)}, server={"name": "weather"}).save(path)

    loaded = Lockfile.load(path)
    assert loaded.tools["get_weather"].definition == TOOL
    assert loaded.server == {"name": "weather"}
    assert [p.name for p in tmp_path.iterdir()] == ["ledgerline.lock"], "no temporary files left behind"


def test_edited_definition_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "ledgerline.lock"
    Lockfile(tools={"get_weather": PinnedTool.of(TOOL)}).save(path)
    data = json.loads(path.read_text())
    data["tools"]["get_weather"]["definition"]["description"] = "something else"
    path.write_text(json.dumps(data))

    with pytest.raises(LockfileError, match="does not match"):
        Lockfile.load(path)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        pytest.param(None, "not found", id="missing"),
        pytest.param("{not json", "cannot read", id="bad-json"),
        pytest.param('{"version": 99}', "unsupported", id="wrong-version"),
        pytest.param('{"version": 1, "tools": {"t": {"sha256": "x"}}}', "no definition", id="no-definition"),
    ],
)
def test_bad_lockfiles(tmp_path: Path, content: str | None, message: str) -> None:
    path = tmp_path / "ledgerline.lock"
    if content is not None:
        path.write_text(content)
    with pytest.raises(LockfileError, match=message):
        Lockfile.load(path)

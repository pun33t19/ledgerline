"""``ledgerline pin`` as a person uses it: review, confirm, write the lock file."""

import io
import json
from pathlib import Path

import pytest

from ledgerline.cli import build_parser, main, run_pin, split_command
from ledgerline.pin.lockfile import Lockfile
from tests.conftest import BIN

WEATHER = [str(BIN / "demo-weather")]
RUGPULL = [str(BIN / "demo-rugpull")]


def pin(lock: Path, command: list[str], *flags: str) -> tuple[int, str]:
    args = build_parser().parse_args(["pin", "--lock", str(lock), *flags])
    out = io.StringIO()
    return run_pin(args, command, out), out.getvalue()


def test_pin_shows_full_definitions_and_writes_lock(tmp_path: Path) -> None:
    lock = tmp_path / "ledgerline.lock"
    code, text = pin(lock, WEATHER, "--yes")

    assert code == 0
    assert "[NEW] get_weather" in text
    assert '"description": "Get the current weather in a given location"' in text
    assert set(Lockfile.load(lock).tools) == {"get_weather"}
    assert json.loads(lock.read_text())["server"] == {"name": "weather", "version": "0.1.0"}


def test_repinning_unchanged_server_reports_up_to_date(tmp_path: Path) -> None:
    lock = tmp_path / "ledgerline.lock"
    pin(lock, WEATHER, "--yes")
    code, text = pin(lock, WEATHER, "--yes")
    assert code == 0
    assert "is up to date" in text
    assert "Unchanged: get_weather" in text


def test_pin_shows_changes_against_existing_lock(tmp_path: Path) -> None:
    lock = tmp_path / "ledgerline.lock"
    pin(lock, WEATHER, "--yes")
    code, text = pin(lock, RUGPULL, "--yes")  # a completely different server
    assert code == 0
    assert "[NEW] get_fact_of_the_day" in text
    assert "[REMOVED] get_weather" in text
    assert set(Lockfile.load(lock).tools) == {"get_fact_of_the_day"}


def test_declining_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = tmp_path / "ledgerline.lock"
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    code, text = pin(lock, WEATHER)
    assert code == 1
    assert "Nothing written" in text
    assert not lock.exists()


def test_split_command() -> None:
    assert split_command(["proxy", "stdio", "--tofu", "--", "srv", "--x"]) == (
        ["proxy", "stdio", "--tofu"],
        ["srv", "--x"],
    )
    assert split_command(["pin", "--http", "u"]) == (["pin", "--http", "u"], [])


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["pin", "--http", "http://x", "--", "srv"], id="pin-both-targets"),
        pytest.param(["pin"], id="pin-no-target"),
        pytest.param(["proxy", "stdio"], id="stdio-without-command"),
        pytest.param(["proxy", "http", "--upstream", "http://x", "--", "srv"], id="http-with-command"),
    ],
)
def test_usage_errors_exit_2(argv: list[str]) -> None:
    assert main(argv) == 2

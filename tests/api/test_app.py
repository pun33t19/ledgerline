"""The Lab API: security first (token, Host, Origin, headers), then runs and live events."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ledgerline.api import app as app_module
from ledgerline.api.app import create_app
from ledgerline.api.security import SESSION_COOKIE, LocalGuard, loopback_hosts, loopback_origins
from ledgerline.sim.coverage import Coverage

TOKEN = "test-token-123"
PORT = 8765
HOST = f"127.0.0.1:{PORT}"
ORIGIN = f"http://{HOST}"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
WS = {**AUTH, "Host": HOST}  # the test client's WebSockets default to Host "testserver"


def make_client(static_dir: Path | None = None) -> TestClient:
    guard = LocalGuard(
        allowed_hosts=loopback_hosts(PORT), allowed_origins=loopback_origins(PORT), token=TOKEN
    )
    app = create_app(guard, static_dir or Path("/nonexistent"))
    return TestClient(app, base_url=f"http://{HOST}")


@pytest.fixture
def client() -> Iterator[TestClient]:
    with make_client() as c:
        yield c


# --- security -------------------------------------------------------------------


def test_health_needs_no_token(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_api_requires_token(client: TestClient) -> None:
    assert client.get("/api/scenarios").status_code == 401
    assert client.get("/api/scenarios", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/scenarios", headers=AUTH).status_code == 200


def test_session_cookie_flow(client: TestClient) -> None:
    assert client.post("/api/session", json={"token": "wrong"}).status_code == 401
    response = client.post("/api/session", json={"token": TOKEN})
    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE}={TOKEN}" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert client.get("/api/scenarios").status_code == 200  # cookie now carried automatically


@pytest.mark.parametrize("host", ["evil.example:8765", "127.0.0.1:9999", "attacker.test"])
def test_dns_rebinding_host_is_rejected(client: TestClient, host: str) -> None:
    response = client.get("/api/health", headers={"Host": host})
    assert response.status_code == 403
    assert "Host not allowed" in response.text


def test_foreign_origin_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/runs", json={"scenario_id": "rug-pull"}, headers={**WS, "Origin": "https://evil.example"}
    )
    assert response.status_code == 403
    ok = client.get("/api/scenarios", headers={**AUTH, "Origin": ORIGIN})
    assert ok.status_code == 200


def test_security_headers(client: TestClient) -> None:
    headers = client.get("/api/health").headers
    assert "default-src 'self'" in headers["content-security-policy"]
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert headers["x-frame-options"] == "DENY"
    assert headers["x-content-type-options"] == "nosniff"


def test_websocket_rejects_foreign_origin(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(
            "/api/runs/x/events", headers={**WS, "Origin": "https://evil.example"}
        ) as ws,
    ):
        ws.receive_text()


# --- scenarios and runs ---------------------------------------------------------------


def test_scenarios(client: TestClient) -> None:
    scenarios = client.get("/api/scenarios", headers=AUTH).json()
    ids = [s["id"] for s in scenarios]
    assert ids[:2] == ["baseline-weather", "tool-poisoning"]
    rug = next(s for s in scenarios if s["id"] == "silent-rug-pull")
    assert rug["expected_protected"] == "safe"
    assert rug["steps"][:2] == ["connect (server/discover)", "list tools"]


def test_unknown_scenario(client: TestClient) -> None:
    assert client.post("/api/runs", json={"scenario_id": "nope"}, headers=AUTH).status_code == 404


def test_run_streams_events_to_completion(client: TestClient) -> None:
    started = client.post("/api/runs", json={"scenario_id": "silent-rug-pull"}, headers=AUTH).json()
    events: list[dict[str, Any]] = []
    with client.websocket_connect(
        f"/api/runs/{started['run_id']}/events", headers={**WS, "Origin": ORIGIN}
    ) as ws:
        while True:
            event = json.loads(ws.receive_text())
            events.append(event)
            if event["type"] == "run_finished":
                break
    types = [e["type"] for e in events]
    assert types[0] == "run_started"
    assert types[-1] == "run_finished"
    assert events[-1]["status"] == "finished"
    outcomes = {e["mode"]: e for e in events if e["type"] == "outcome"}
    assert outcomes["unprotected"]["verdict"] == "harmed"
    assert outcomes["protected"]["verdict"] == "safe"

    record = client.get(f"/api/runs/{started['run_id']}", headers=AUTH).json()
    assert record["status"] == "finished"
    assert len(record["events"]) == len(events)
    assert client.get("/api/runs", headers=AUTH).json()[0]["run_id"] == started["run_id"]


def test_coverage_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake() -> Coverage:
        return Coverage(controls=["pinning"], rows=[])

    monkeypatch.setattr(app_module, "compute_coverage", fake)
    assert client.get("/api/coverage", headers=AUTH).json() == {"controls": ["pinning"], "rows": []}


# --- serving the UI -----------------------------------------------------------------------


def test_ui_not_built() -> None:
    with make_client() as c:
        response = c.get("/")
    assert response.status_code == 503
    assert "make web-build" in response.text


def test_spa_fallback_and_assets(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html>lab</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    with make_client(tmp_path) as c:
        assert c.get("/").text == "<html>lab</html>"
        assert c.get("/runs/abc").text == "<html>lab</html>"  # client-side route
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/../../etc/passwd").text == "<html>lab</html>"  # no path traversal
        assert c.get("/api/nope", headers=AUTH).status_code == 404

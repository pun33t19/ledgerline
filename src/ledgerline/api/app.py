"""FastAPI app behind the Lab UI.

    GET  /api/health                    liveness (no token)
    POST /api/session                   exchange the printed token for a session cookie
    GET  /api/scenarios                 the scenario catalogue
    POST /api/runs                      start a run → {run_id}
    GET  /api/runs                      recent runs
    GET  /api/runs/{id}                 a run with all its events so far
    WS   /api/runs/{id}/events          live events (replays earlier ones first)
    GET  /api/coverage                  which control stops which attack (measured, cached)

Everything else serves the built React app (web/ → src/ledgerline/api/static).
"""

from __future__ import annotations

import contextlib
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import anyio
import anyio.abc
from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field, TypeAdapter

from ledgerline import __version__
from ledgerline.api.security import SESSION_COOKIE, LocalGuard, LocalGuardMiddleware
from ledgerline.sim.catalog import BY_ID, SCENARIOS
from ledgerline.sim.coverage import Coverage, compute_coverage
from ledgerline.sim.events import Controls, Outcome, RunEvent, RunFinished, RunStarted, Verdict
from ledgerline.sim.runner import Runner
from ledgerline.sim.scenario import CallTool, Discover, ListTools, ObeyNewInstructions, Scenario, SendRaw

STATIC_DIR = Path(__file__).parent / "static"
MAX_RUNS = 50
_EVENT: TypeAdapter[Any] = TypeAdapter(RunEvent)


# --- API models ------------------------------------------------------------------


class ScenarioInfo(BaseModel):
    id: str
    title: str
    category: str
    difficulty: str
    summary: str
    story: str
    incident: str
    owasp_mcp: list[str]
    owasp_asi: list[str]
    honest_note: str
    expected_unprotected: Verdict
    expected_protected: Verdict
    controls_that_matter: list[str]
    steps: list[str]


class StartRun(BaseModel):
    scenario_id: str
    controls: Controls = Field(default_factory=Controls)


class RunSummary(BaseModel):
    run_id: str
    scenario_id: str
    controls: Controls
    status: Literal["running", "finished", "failed"]
    started_at: float
    outcomes: dict[str, Outcome]


class RunRecord(RunSummary):
    events: list[RunEvent]


class SessionRequest(BaseModel):
    token: str


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = __version__


def _step_title(step: Any) -> str:
    match step:
        case Discover():
            return "connect (server/discover)"
        case ListTools():
            return "list tools"
        case CallTool(name=name, only_if_listed=only):
            return f"call {name}" + (" (only if still listed)" if only else "")
        case ObeyNewInstructions():
            return "follow instructions found in tool descriptions"
        case SendRaw(title=title):
            return str(title)
    return type(step).__name__


def scenario_info(s: Scenario) -> ScenarioInfo:
    return ScenarioInfo(
        id=s.id,
        title=s.title,
        category=s.category,
        difficulty=s.difficulty,
        summary=s.summary,
        story=s.story,
        incident=s.incident,
        owasp_mcp=list(s.owasp_mcp),
        owasp_asi=list(s.owasp_asi),
        honest_note=s.honest_note,
        expected_unprotected=s.expected_unprotected,
        expected_protected=s.expected_protected,
        controls_that_matter=list(s.controls_that_matter),
        steps=["connect (server/discover)", "list tools", *(_step_title(x) for x in s.steps)],
    )


# --- Runs -------------------------------------------------------------------------


class _Run:
    def __init__(self, run_id: str, scenario: Scenario, controls: Controls) -> None:
        self.run_id, self.scenario, self.controls = run_id, scenario, controls
        self.status: Literal["running", "finished", "failed"] = "running"
        self.started_at = time.time()
        self.events: list[Any] = []
        self.outcomes: dict[str, Outcome] = {}
        self.changed = anyio.Event()

    def add(self, event: Any) -> None:
        self.events.append(event)
        if isinstance(event, Outcome):
            self.outcomes[event.mode] = event
        changed, self.changed = self.changed, anyio.Event()
        changed.set()  # wake every live viewer

    def summary(self) -> RunSummary:
        return RunSummary(
            run_id=self.run_id,
            scenario_id=self.scenario.id,
            controls=self.controls,
            status=self.status,
            started_at=self.started_at,
            outcomes=self.outcomes,
        )


class RunManager:
    def __init__(self) -> None:
        self.runs: dict[str, _Run] = {}
        self.tg: anyio.abc.TaskGroup | None = None
        self._coverage: Coverage | None = None
        self._coverage_lock = anyio.Lock()

    def start(self, scenario: Scenario, controls: Controls) -> _Run:
        if self.tg is None:
            raise RuntimeError("RunManager used outside the app lifespan")
        run = _Run(secrets.token_hex(6), scenario, controls)
        self.runs[run.run_id] = run
        while len(self.runs) > MAX_RUNS:  # forget the oldest
            self.runs.pop(next(iter(self.runs)))
        self.tg.start_soon(self._execute, run)
        return run

    async def _execute(self, run: _Run) -> None:
        runner = Runner(run.scenario, run.controls, run.add)
        runner.emit(RunStarted(run_id=run.run_id, scenario_id=run.scenario.id, controls=run.controls))
        try:
            await runner.run()
            run.status = "finished"
            runner.emit(RunFinished(status="finished"))
        except Exception as e:  # report any failure to the viewer instead of dying silently
            run.status = "failed"
            runner.emit(RunFinished(status="failed", error=f"{type(e).__name__}: {e}"))

    async def coverage(self) -> Coverage:
        async with self._coverage_lock:
            if self._coverage is None:
                self._coverage = await compute_coverage()
            return self._coverage


# --- App --------------------------------------------------------------------------


def create_app(guard: LocalGuard, static_dir: Path = STATIC_DIR) -> FastAPI:
    manager = RunManager()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with anyio.create_task_group() as tg:
            manager.tg = tg
            yield
            tg.cancel_scope.cancel()

    app = FastAPI(title="Ledgerline", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.get("/api/health")
    async def health() -> Health:
        return Health()

    @app.post("/api/session", status_code=204)
    async def session(body: SessionRequest, response: Response) -> None:
        if not guard.token_ok([body.token]):
            raise HTTPException(401, "invalid token")
        response.set_cookie(SESSION_COOKIE, body.token, httponly=True, samesite="strict", path="/")

    @app.get("/api/scenarios")
    async def scenarios() -> list[ScenarioInfo]:
        return [scenario_info(s) for s in SCENARIOS]

    @app.post("/api/runs")
    async def start_run(body: StartRun) -> RunSummary:
        scenario = BY_ID.get(body.scenario_id)
        if scenario is None:
            raise HTTPException(404, f"unknown scenario {body.scenario_id!r}")
        return manager.start(scenario, body.controls).summary()

    @app.get("/api/runs")
    async def list_runs() -> list[RunSummary]:
        return [r.summary() for r in reversed(manager.runs.values())]

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> RunRecord:
        run = manager.runs.get(run_id)
        if run is None:
            raise HTTPException(404, "unknown run")
        return RunRecord(**run.summary().model_dump(), events=list(run.events))

    @app.websocket("/api/runs/{run_id}/events")
    async def run_events(ws: WebSocket, run_id: str) -> None:
        await ws.accept()
        run = manager.runs.get(run_id)
        if run is None:
            await ws.close(code=4404, reason="unknown run")
            return
        sent = 0
        with contextlib.suppress(WebSocketDisconnect):
            while True:
                changed = run.changed
                # Count each event as it is sent: more may arrive while we await the socket.
                while sent < len(run.events):
                    await ws.send_text(_EVENT.dump_json(run.events[sent]).decode())
                    sent += 1
                if run.events and isinstance(run.events[-1], RunFinished):
                    break
                await changed.wait()
            await ws.close()

    @app.get("/api/coverage")
    async def coverage() -> Coverage:
        return await manager.coverage()

    # --- The built UI (single-page app: unknown paths get index.html) ---
    @app.get("/{path:path}", include_in_schema=False)
    def ui(path: str) -> Response:  # plain def: FastAPI runs it in a thread (it touches the disk)
        if path.startswith("api/"):
            raise HTTPException(404)
        index = static_dir / "index.html"
        if not index.exists():
            return HTMLResponse(
                "<h1>Ledgerline UI not built</h1><p>Run <code>make web-build</code>, then restart "
                "<code>ledgerline ui</code>.</p>",
                status_code=503,
            )
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and static_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)

    app.add_middleware(LocalGuardMiddleware, guard=guard)
    return app

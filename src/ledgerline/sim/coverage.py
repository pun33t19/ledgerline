"""Which control stops which attack, measured by re-running each scenario with one control off."""

from __future__ import annotations

from typing import Literal

import anyio
from pydantic import BaseModel

from ledgerline.sim.catalog import SCENARIOS
from ledgerline.sim.events import Controls, Verdict
from ledgerline.sim.runner import Runner
from ledgerline.sim.scenario import Scenario

CONTROL_KEYS = ("pinning", "verify_each_call", "strict_parsing")
CellStatus = Literal["required", "not_needed", "not_stopped"]


class CoverageRow(BaseModel):
    scenario_id: str
    title: str
    category: str
    unprotected: Verdict
    protected: Verdict
    cells: dict[str, CellStatus]
    owasp_mcp: list[str]
    owasp_asi: list[str]


class Coverage(BaseModel):
    controls: list[str]
    rows: list[CoverageRow]


async def _protected_verdict(scenario: Scenario, controls: Controls) -> tuple[Verdict, Verdict]:
    out = await Runner(scenario, controls, lambda _e: None).run()
    return out["unprotected"].verdict, out["protected"].verdict


async def _row(scenario: Scenario, limiter: anyio.CapacityLimiter) -> CoverageRow:
    async with limiter:
        unprotected, protected = await _protected_verdict(scenario, Controls())
    cells: dict[str, CellStatus] = {}
    for key in CONTROL_KEYS:
        if protected == "harmed":
            cells[key] = "not_stopped"
            continue
        async with limiter:
            _, without = await _protected_verdict(scenario, Controls(**{key: False}))
        cells[key] = "required" if without == "harmed" else "not_needed"
    return CoverageRow(
        scenario_id=scenario.id,
        title=scenario.title,
        category=scenario.category,
        unprotected=unprotected,
        protected=protected,
        cells=cells,
        owasp_mcp=list(scenario.owasp_mcp),
        owasp_asi=list(scenario.owasp_asi),
    )


async def compute_coverage(scenarios: tuple[Scenario, ...] = SCENARIOS, parallel: int = 3) -> Coverage:
    limiter = anyio.CapacityLimiter(parallel)
    rows: dict[str, CoverageRow] = {}

    async def fill(s: Scenario) -> None:
        rows[s.id] = await _row(s, limiter)

    async with anyio.create_task_group() as tg:
        for s in scenarios:
            tg.start_soon(fill, s)
    return Coverage(controls=list(CONTROL_KEYS), rows=[rows[s.id] for s in scenarios])

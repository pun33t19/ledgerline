import { describe, expect, it } from "vitest";
import type { RunEvent } from "../api/types";
import { applyEvent, initialRun, latestMenu } from "./runState";

const base = { seq: 0, t_ms: 0 };
const run = (events: RunEvent[]) => events.reduce(applyEvent, initialRun());

describe("applyEvent", () => {
  it("tracks status from start to finish", () => {
    const controls = { pinning: true, verify_each_call: true, strict_parsing: true };
    expect(run([]).status).toBe("connecting");
    const started = run([{ ...base, type: "run_started", run_id: "r1", scenario_id: "rug-pull", controls }]);
    expect(started.status).toBe("running");
    expect(started.scenarioId).toBe("rug-pull");
    const done = applyEvent(started, { ...base, type: "run_finished", status: "finished" });
    expect(done.status).toBe("finished");
  });

  it("keeps each mode's entries separate, in order", () => {
    const view = run([
      {
        ...base,
        seq: 1,
        type: "step",
        mode: "unprotected",
        index: 1,
        title: "connect",
        status: "done",
        detail: "",
      },
      {
        ...base,
        seq: 2,
        type: "message",
        mode: "protected",
        source: "host",
        target: "ledgerline",
        internal: false,
        kind: "request",
        summary: "tools/list",
      },
      {
        ...base,
        seq: 3,
        type: "decision",
        mode: "protected",
        action: "blocked",
        control: "verify-before-call",
        reason: "tool_changed",
      },
      { ...base, seq: 4, type: "exfiltration", mode: "unprotected", via: "server-side", data: "FAKE" },
    ]);
    expect(view.modes.unprotected.entries.map((e) => e.seq)).toEqual([1, 4]);
    expect(view.modes.protected.entries.map((e) => e.seq)).toEqual([2, 3]);
    expect(view.modes.protected.lastMessage?.summary).toBe("tools/list");
    expect(view.modes.protected.decisions).toHaveLength(1);
    expect(view.modes.unprotected.stolen[0]?.data).toBe("FAKE");
  });

  it("records outcomes and the latest menu", () => {
    const tool = { name: "t", description: "d", sha256: "abc", definition: {} };
    const view = run([
      { ...base, type: "menu", mode: "protected", step: 2, tools: [] },
      { ...base, type: "menu", mode: "protected", step: 6, tools: [tool] },
      {
        ...base,
        type: "outcome",
        mode: "protected",
        verdict: "safe",
        headline: "Stopped",
        stopped_by: ["tool-pinning"],
      },
    ]);
    expect(latestMenu(view.modes.protected)).toEqual([tool]);
    expect(view.modes.protected.outcome?.verdict).toBe("safe");
  });
});

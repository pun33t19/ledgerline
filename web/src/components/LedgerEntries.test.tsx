import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Entry } from "../lib/runState";
import { entryLabel, humanize, LedgerEntries } from "./LedgerEntries";

const base = { seq: 1, t_ms: 420 };
const decision: Entry = {
  ...base,
  type: "decision",
  mode: "protected",
  action: "replaced",
  control: "tool-pinning",
  reason: "hid changed or unpinned tool(s): get_fact_of_the_day",
};
const message: Entry = {
  ...base,
  seq: 2,
  type: "message",
  mode: "protected",
  source: "ledgerline",
  target: "server",
  internal: true,
  kind: "request",
  summary: "tools/list",
};

describe("humanize", () => {
  it("turns codes into words but leaves free text alone", () => {
    expect(humanize("tool_changed")).toBe("tool changed");
    expect(humanize("call_blocked:tool_changed")).toBe("call blocked tool changed");
    expect(humanize("hid tool(s): get_fact_of_the_day")).toBe("hid tool(s): get_fact_of_the_day");
  });
});

describe("entryLabel", () => {
  it("names the control in plain words and keeps tool names intact", () => {
    expect(entryLabel(decision)).toEqual({
      who: "Tool pinning",
      what: "changed the reply: hid changed or unpinned tool(s): get_fact_of_the_day",
      tone: "guard",
    });
  });

  it("marks Ledgerline's own checks", () => {
    expect(entryLabel(message).who).toBe("Ledgerline to Server, Ledgerline's own check");
  });
});

describe("LedgerEntries", () => {
  it("hides protocol messages unless asked, and reports clicks", async () => {
    const onSelect = vi.fn();
    const { rerender } = render(
      <LedgerEntries entries={[decision, message]} showMessages={false} onSelect={onSelect} />,
    );
    expect(screen.queryByText("tools/list")).not.toBeInTheDocument();
    await userEvent.click(screen.getByText(/changed the reply/));
    expect(onSelect).toHaveBeenCalledWith(decision);

    rerender(<LedgerEntries entries={[decision, message]} showMessages={true} onSelect={onSelect} />);
    expect(screen.getByText("tools/list")).toBeInTheDocument();
    expect(screen.getAllByText("0.42s", { exact: false })).toHaveLength(2);
  });
});

import * as Tabs from "@radix-ui/react-tabs";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { useScenarios, useStartRun } from "../api/queries";
import type { Controls, Mode } from "../api/types";
import { useRunEvents } from "../api/useRunEvents";
import { AttackPath } from "../components/AttackPath";
import { ControlSwitches } from "../components/ControlSwitches";
import { FlowStrip } from "../components/FlowStrip";
import { Inspector } from "../components/Inspector";
import { LedgerEntries } from "../components/LedgerEntries";
import { Tags } from "../components/Tags";
import { ToolLens } from "../components/ToolLens";
import { Verdict } from "../components/Verdict";
import { ALL_ON } from "../lib/controls";
import { type Entry, latestMenu } from "../lib/runState";
import { Problem } from "./Problem";

const COLUMN_TITLE: Record<Mode, string> = {
  unprotected: "Without Ledgerline",
  protected: "With Ledgerline",
};

export function RunPage() {
  const { runId } = useParams();
  const view = useRunEvents(runId);
  const scenarios = useScenarios();
  const start = useStartRun();
  const navigate = useNavigate();
  const [controls, setControls] = useState<Controls>(ALL_ON);
  const [selected, setSelected] = useState<Entry | null>(null);
  const [showMessages, setShowMessages] = useState(false);

  useEffect(() => {
    if (view.controls) setControls(view.controls);
  }, [view.controls]);

  if (scenarios.error) return <Problem error={scenarios.error} />;
  const scenario = scenarios.data?.find((s) => s.id === view.scenarioId);
  const running = view.status === "connecting" || view.status === "running";
  const changed = JSON.stringify(controls) !== JSON.stringify(view.controls ?? ALL_ON);

  return (
    <>
      <section className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <div className="max-w-prose">
          <p className="text-sm text-ink-muted">{scenario?.category ?? "Attack"}</p>
          <h1 className="text-3xl font-bold tracking-tight">{scenario?.title ?? "Loading…"}</h1>
          {scenario && <p className="mt-3">{scenario.story}</p>}
          {scenario?.honest_note && (
            <p className="mt-3 rounded-sm border-l-4 border-rule-strong bg-paper-raised px-3 py-2 text-sm">
              {scenario.honest_note}
            </p>
          )}
          {scenario && (
            <div className="mt-4">
              <Tags owaspMcp={scenario.owasp_mcp} owaspAsi={scenario.owasp_asi} />
            </div>
          )}
        </div>
        <div>
          <ControlSwitches
            value={controls}
            onChange={setControls}
            relevant={scenario?.controls_that_matter ?? []}
          />
          <button
            type="button"
            disabled={!scenario || start.isPending || running}
            onClick={async () => {
              if (!scenario) return;
              const run = await start.mutateAsync({ scenario_id: scenario.id, controls });
              navigate(`/runs/${run.run_id}`);
            }}
            className="mt-4 rounded border-2 border-guard bg-guard px-4 py-2 font-bold text-paper hover:opacity-90 disabled:opacity-50"
          >
            {changed ? "Run with these controls" : "Run again"}
          </button>
        </div>
      </section>

      {view.status === "failed" && <p className="mt-6 font-bold text-loss">The run failed: {view.error}</p>}

      <Tabs.Root defaultValue="ledger" className="mt-10">
        <Tabs.List aria-label="Run views" className="flex gap-6 border-b border-rule">
          {[
            ["ledger", "Side by side"],
            ["tools", "What the model reads"],
          ].map(([value, label]) => (
            <Tabs.Trigger
              key={value}
              value={value as string}
              className="-mb-px border-b-2 border-transparent pb-2 text-ink-muted data-[state=active]:border-guard data-[state=active]:font-bold data-[state=active]:text-ink"
            >
              {label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="ledger" className="pt-6">
          <label className="mb-4 flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={showMessages}
              onChange={(e) => setShowMessages(e.target.checked)}
            />
            Show every protocol message
          </label>
          <div className="grid gap-y-10 md:grid-cols-2">
            {(["unprotected", "protected"] as const).map((mode) => (
              <section
                key={mode}
                aria-labelledby={`col-${mode}`}
                className={mode === "protected" ? "md:double-rule md:pl-6" : "md:pr-6"}
              >
                <h2 id={`col-${mode}`} className="text-xl font-bold">
                  {COLUMN_TITLE[mode]}
                </h2>
                <FlowStrip mode={mode} view={view.modes[mode]} />
                <Verdict view={view.modes[mode]} running={running} />
                <AttackPath
                  mode={mode}
                  view={view.modes[mode]}
                  baseline={scenario?.id === "baseline-weather"}
                />
                <LedgerEntries
                  entries={view.modes[mode].entries}
                  showMessages={showMessages}
                  onSelect={setSelected}
                />
              </section>
            ))}
          </div>
        </Tabs.Content>

        <Tabs.Content value="tools" className="pt-6">
          <ToolLens
            pinned={view.pinned}
            current={latestMenu(view.modes.unprotected)}
            shownWithLedgerline={latestMenu(view.modes.protected)}
          />
        </Tabs.Content>
      </Tabs.Root>

      <Inspector entry={selected} onClose={() => setSelected(null)} />
    </>
  );
}

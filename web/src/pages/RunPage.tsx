import * as Tabs from "@radix-ui/react-tabs";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useScenarios, useStartRun } from "../api/queries";
import type { Controls, Mode } from "../api/types";
import { useRunEvents } from "../api/useRunEvents";
import { AttackStage } from "../components/AttackStage";
import { ControlSwitches } from "../components/ControlSwitches";
import { Inspector } from "../components/Inspector";
import { LedgerChain } from "../components/LedgerChain";
import { LedgerEntries } from "../components/LedgerEntries";
import { Tags } from "../components/Tags";
import { ToolLens } from "../components/ToolLens";
import { Verdict } from "../components/Verdict";
import { ALL_ON } from "../lib/controls";
import { type Entry, latestMenu, type ModeView } from "../lib/runState";
import { buildStory } from "../lib/story";
import { Problem } from "./Problem";

const COLUMN_TITLE: Record<Mode, string> = {
  unprotected: "Without Ledgerline",
  protected: "With Ledgerline",
};

function SideStatus({ view }: { view: ModeView }) {
  const verdict = view.outcome?.verdict;
  if (!verdict) return <span className="text-ink-muted">running</span>;
  return verdict === "harmed" ? (
    <span className="text-loss">secret stolen</span>
  ) : (
    <span className="text-safe">safe</span>
  );
}

export function RunPage() {
  const { runId } = useParams();
  const view = useRunEvents(runId);
  const scenarios = useScenarios();
  const start = useStartRun();
  const navigate = useNavigate();
  const [controls, setControls] = useState<Controls>(ALL_ON);
  const [selected, setSelected] = useState<Entry | null>(null);
  const [showMessages, setShowMessages] = useState(false);
  const [side, setSide] = useState<Mode>("unprotected");
  const [watchedUnprotected, setWatchedUnprotected] = useState(false);

  useEffect(() => {
    if (view.controls) setControls(view.controls);
  }, [view.controls]);

  // A new run starts on the unprotected side again.
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset only when the run changes
  useEffect(() => {
    setSide("unprotected");
    setWatchedUnprotected(false);
  }, [runId]);

  const stories = useMemo(
    () => ({
      unprotected: buildStory("unprotected", view.modes.unprotected),
      protected: buildStory("protected", view.modes.protected),
    }),
    [view.modes],
  );
  const onFinished = useCallback(() => {
    if (side === "unprotected") setWatchedUnprotected(true);
  }, [side]);

  if (scenarios.error) return <Problem error={scenarios.error} />;
  const scenario = scenarios.data?.find((s) => s.id === view.scenarioId);
  const running = view.status === "connecting" || view.status === "running";
  const changed = JSON.stringify(controls) !== JSON.stringify(view.controls ?? ALL_ON);

  return (
    <>
      <Link to="/" className="text-sm text-ink-muted hover:text-ink">
        All attacks
      </Link>
      <section className="mt-4 max-w-4xl">
        <p className="text-ink-muted">{scenario?.category ?? "Attack"}</p>
        <h1 className="display mt-1 text-[2.6rem] text-balance md:text-[3.8rem]">
          {scenario?.title ?? "Loading…"}
        </h1>
        {scenario && <p className="mt-4 max-w-[42rem] text-lg text-ink-muted">{scenario.story}</p>}
      </section>

      <section aria-label="Attack replay" className="glass mt-10 rounded-[28px] p-4 md:p-7">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div
            role="tablist"
            aria-label="Which side to watch"
            className="grid w-full grid-cols-2 rounded-2xl bg-paper-raised p-1 sm:flex sm:w-auto sm:rounded-full"
          >
            {(["unprotected", "protected"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                role="tab"
                aria-selected={side === mode}
                onClick={() => setSide(mode)}
                className="flex flex-col items-start gap-x-2 rounded-xl px-3 py-2 text-left text-sm transition-colors aria-selected:bg-button aria-selected:text-button-ink sm:flex-row sm:items-center sm:rounded-full sm:px-4"
              >
                <span className="font-medium">{COLUMN_TITLE[mode]}</span>
                <span className="opacity-90">
                  <SideStatus view={view.modes[mode]} />
                </span>
              </button>
            ))}
          </div>
          {side === "unprotected" && watchedUnprotected && (
            <button
              type="button"
              onClick={() => setSide("protected")}
              className="h-10 rounded-full bg-button px-5 text-sm font-medium text-button-ink"
            >
              Now watch it with Ledgerline
            </button>
          )}
          <p className="hidden text-sm text-ink-muted md:block">Drag the map to turn it.</p>
        </div>
        <div className="mt-4">
          <AttackStage
            key={`${runId}-${side}`}
            mode={side}
            beats={stories[side]}
            running={running}
            onFinished={onFinished}
          />
        </div>
      </section>

      {view.status === "failed" && <p className="mt-6 font-medium text-loss">The run failed: {view.error}</p>}

      <section className="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className="space-y-5">
          {scenario?.honest_note && (
            <div className="rounded-2xl border border-rule bg-paper-raised px-5 py-4">
              <p className="font-medium">Honest limit</p>
              <p className="mt-1 text-ink-muted">{scenario.honest_note}</p>
            </div>
          )}
          {scenario && <Tags owaspMcp={scenario.owasp_mcp} owaspAsi={scenario.owasp_asi} />}
          {scenario?.incident && (
            <p className="text-sm text-ink-muted">Seen in the wild: {scenario.incident}</p>
          )}
        </div>
        <div className="glass rounded-3xl p-6">
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
            className="mt-6 h-11 w-full rounded-full bg-button px-5 font-medium text-button-ink transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {changed ? "Run with these controls" : "Run again"}
          </button>
        </div>
      </section>

      <Tabs.Root defaultValue="ledger" className="mt-14">
        <Tabs.List aria-label="Run details" className="flex gap-1 border-b border-rule">
          {[
            ["ledger", "Event log"],
            ["chain", "Ledger"],
            ["tools", "What the model reads"],
          ].map(([value, label]) => (
            <Tabs.Trigger
              key={value}
              value={value as string}
              className="-mb-px border-b-2 border-transparent px-3 pb-3 text-ink-muted transition-colors hover:text-ink data-[state=active]:border-ink data-[state=active]:text-ink"
            >
              {label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="ledger" className="pt-6">
          <label className="mb-5 flex items-center gap-2 text-sm text-ink-muted">
            <input
              type="checkbox"
              checked={showMessages}
              onChange={(e) => setShowMessages(e.target.checked)}
              className="accent-[var(--guard)]"
            />
            Show every protocol message
          </label>
          <div className="grid gap-x-8 gap-y-10 md:grid-cols-2">
            {(["unprotected", "protected"] as const).map((mode) => (
              <section key={mode} aria-labelledby={`col-${mode}`}>
                <h2 id={`col-${mode}`} className="display text-[1.8rem]">
                  {COLUMN_TITLE[mode]}
                </h2>
                <div className="mt-3">
                  <Verdict view={view.modes[mode]} running={running} />
                </div>
                <div className="mt-4">
                  <LedgerEntries
                    entries={view.modes[mode].entries}
                    showMessages={showMessages}
                    onSelect={setSelected}
                  />
                </div>
              </section>
            ))}
          </div>
        </Tabs.Content>

        <Tabs.Content value="chain" className="pt-6">
          <LedgerChain key={runId} entries={view.ledger} running={running} />
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

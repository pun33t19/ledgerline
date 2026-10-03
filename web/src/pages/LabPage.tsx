import { useNavigate } from "react-router";
import { useScenarios, useStartRun } from "../api/queries";
import type { Verdict } from "../api/types";
import { ALL_ON } from "../lib/controls";
import { Problem } from "./Problem";

function Expected({ verdict }: { verdict: Verdict }) {
  return verdict === "harmed" ? (
    <span className="font-bold text-loss">Secret stolen</span>
  ) : (
    <span className="font-bold text-safe">Safe</span>
  );
}

export function LabPage() {
  const scenarios = useScenarios();
  const start = useStartRun();
  const navigate = useNavigate();

  if (scenarios.error) return <Problem error={scenarios.error} />;

  const run = async (scenarioId: string) => {
    const started = await start.mutateAsync({ scenario_id: scenarioId, controls: ALL_ON });
    navigate(`/runs/${started.run_id}`);
  };

  return (
    <>
      <section className="max-w-3xl">
        <h1 className="text-3xl font-bold tracking-tight md:text-4xl">Run an attack twice</h1>
        <p className="mt-3 text-lg">
          Each attack runs against a deliberately malicious tool server two ways at once: straight to the
          server, and through Ledgerline. Watch both sides, then switch controls off to see which one stops
          what.
        </p>
        <p className="mt-2 text-ink-muted">
          The agent is scripted to obey whatever tool descriptions say, so every run is repeatable. The only
          secret in play is a fake value in a temporary file.
        </p>
      </section>

      {/* Phones: one ruled entry per attack. */}
      <ol className="ruled mt-8 border-y border-rule md:hidden" aria-label="Attacks you can run">
        {scenarios.isPending && <li className="py-6 text-ink-muted">Loading attacks…</li>}
        {scenarios.data?.map((s) => (
          <li key={s.id} className="py-4">
            <p className="text-lg font-bold">{s.title}</p>
            <p className="text-ink-muted">{s.summary}</p>
            <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
              <div>
                <dt className="text-ink-muted">Without Ledgerline</dt>
                <dd>
                  <Expected verdict={s.expected_unprotected} />
                </dd>
              </div>
              <div className="double-rule pl-3">
                <dt className="text-ink-muted">With Ledgerline</dt>
                <dd>
                  <Expected verdict={s.expected_protected} />
                </dd>
              </div>
            </dl>
            <button
              type="button"
              disabled={start.isPending}
              onClick={() => run(s.id)}
              className="mt-3 rounded border-2 border-guard px-4 py-1.5 font-bold text-guard disabled:opacity-50"
            >
              Run {s.title.toLowerCase()}
            </button>
          </li>
        ))}
      </ol>

      <div className="mt-10 hidden md:block">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">Attacks you can run</caption>
          <thead>
            <tr className="border-b-2 border-rule-strong text-sm text-ink-muted">
              <th scope="col" className="py-2 pr-4 font-normal">
                Attack
              </th>
              <th scope="col" className="py-2 pr-4 font-normal">
                Without Ledgerline
              </th>
              <th scope="col" className="double-rule py-2 pr-4 pl-4 font-normal">
                With Ledgerline
              </th>
              <th scope="col" className="py-2">
                <span className="sr-only">Run</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {scenarios.isPending && (
              <tr>
                <td colSpan={4} className="py-6 text-ink-muted">
                  Loading attacks…
                </td>
              </tr>
            )}
            {scenarios.data?.map((s) => (
              <tr key={s.id} className="border-b border-rule align-top">
                <th scope="row" className="py-4 pr-4 font-normal">
                  <span className="block text-lg font-bold">{s.title}</span>
                  <span className="block max-w-prose text-ink-muted">{s.summary}</span>
                  {s.incident && (
                    <span className="mt-1 block text-sm text-ink-muted">Real-world case: {s.incident}</span>
                  )}
                </th>
                <td className="py-4 pr-4">
                  <Expected verdict={s.expected_unprotected} />
                </td>
                <td className="double-rule py-4 pr-4 pl-4">
                  <Expected verdict={s.expected_protected} />
                  {s.honest_note && (
                    <span className="mt-1 block max-w-xs text-sm text-ink-muted">Not stopped yet</span>
                  )}
                </td>
                <td className="py-4 text-right">
                  <button
                    type="button"
                    disabled={start.isPending}
                    onClick={() => run(s.id)}
                    className="rounded border-2 border-guard px-4 py-1.5 font-bold text-guard hover:bg-guard hover:text-paper disabled:opacity-50"
                  >
                    Run
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {start.error && <Problem error={start.error} />}
    </>
  );
}

import { useNavigate } from "react-router";
import { useScenarios, useStartRun } from "../api/queries";
import type { Verdict } from "../api/types";
import { HeroMap } from "../components/HeroMap";
import { ALL_ON } from "../lib/controls";
import { Problem } from "./Problem";

const FEATURED = "silent-rug-pull";

function Expected({ verdict, label }: { verdict: Verdict; label?: string }) {
  const harmed = verdict === "harmed";
  return (
    <span
      className={`inline-flex items-center gap-2 text-sm font-medium ${harmed ? "text-loss" : "text-safe"}`}
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${harmed ? "bg-loss" : "bg-safe"}`} />
      {label && <span className="sr-only">{label}: </span>}
      {harmed ? "Secret stolen" : "Safe"}
    </span>
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
      <section className="grid items-center gap-6 pt-6 md:pt-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="relative z-10">
          <h1 className="display text-[3.1rem] text-balance md:text-[4.6rem]">
            Watch an AI agent get compromised. Then watch Ledgerline stop it.
          </h1>
          <p className="mt-6 max-w-[38rem] text-lg text-ink-muted">
            Each attack runs twice at once against a deliberately malicious tool server: once straight
            through, once through Ledgerline. Step through what happened on each side.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <button
              type="button"
              disabled={start.isPending || !scenarios.data}
              onClick={() => run(FEATURED)}
              className="h-12 rounded-full bg-button px-6 font-medium text-button-ink transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              Watch a silent rug pull
            </button>
            <span className="max-w-[22rem] text-sm text-ink-muted">
              The agent is scripted to obey every tool description. The only secret is a fake one.
            </span>
          </div>
        </div>
        <div className="relative hidden h-[34rem] lg:block" aria-hidden="true">
          <div
            className="absolute inset-y-0 -right-40 -left-28"
            style={{
              maskImage: "radial-gradient(ellipse 50% 50% at 50% 50%, black 55%, transparent)",
              WebkitMaskImage: "radial-gradient(ellipse 50% 50% at 50% 50%, black 55%, transparent)",
            }}
          >
            <HeroMap />
          </div>
        </div>
      </section>

      <section className="mt-20" aria-labelledby="attacks-heading">
        <h2 id="attacks-heading" className="display text-[2.2rem]">
          Attacks
        </h2>

        {/* Phones: one entry per attack. */}
        <ol className="glass ruled mt-5 rounded-3xl px-5 md:hidden" aria-label="Attacks you can run">
          {scenarios.isPending && <li className="py-6 text-ink-muted">Loading attacks…</li>}
          {scenarios.data?.map((s) => (
            <li key={s.id} className="py-5">
              <p className="text-lg font-medium">{s.title}</p>
              <p className="mt-1 text-ink-muted">{s.summary}</p>
              <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1">
                <span className="text-sm text-ink-muted">
                  Without Ledgerline <Expected verdict={s.expected_unprotected} />
                </span>
                <span className="text-sm text-ink-muted">
                  With Ledgerline <Expected verdict={s.expected_protected} />
                </span>
              </div>
              <button
                type="button"
                disabled={start.isPending}
                onClick={() => run(s.id)}
                className="mt-4 h-10 rounded-full bg-button px-5 text-sm font-medium text-button-ink disabled:opacity-50"
              >
                Run {s.title.toLowerCase()}
              </button>
            </li>
          ))}
        </ol>

        <div className="glass mt-5 hidden overflow-hidden rounded-3xl md:block">
          <table className="w-full border-collapse text-left">
            <caption className="sr-only">Attacks you can run</caption>
            <thead>
              <tr className="border-b border-rule text-sm text-ink-muted">
                <th scope="col" className="py-3.5 pr-4 pl-7 font-normal">
                  Attack
                </th>
                <th scope="col" className="py-3.5 pr-4 font-normal">
                  Without Ledgerline
                </th>
                <th scope="col" className="py-3.5 pr-4 font-normal">
                  With Ledgerline
                </th>
                <th scope="col" className="py-3.5 pr-7">
                  <span className="sr-only">Run</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {scenarios.isPending && (
                <tr>
                  <td colSpan={4} className="px-7 py-6 text-ink-muted">
                    Loading attacks…
                  </td>
                </tr>
              )}
              {scenarios.data?.map((s) => (
                <tr
                  key={s.id}
                  className="border-b border-rule align-top transition-colors last:border-0 hover:bg-paper-raised"
                >
                  <th scope="row" className="py-5 pr-6 pl-7 font-normal">
                    <span className="block text-[17px] font-medium">{s.title}</span>
                    <span className="mt-0.5 block max-w-[34rem] text-ink-muted">{s.summary}</span>
                    {s.incident && (
                      <span className="mt-1.5 block text-sm text-ink-muted/80">
                        Seen in the wild: {s.incident}
                      </span>
                    )}
                  </th>
                  <td className="py-5 pr-4 whitespace-nowrap">
                    <Expected verdict={s.expected_unprotected} />
                  </td>
                  <td className="py-5 pr-4">
                    <Expected verdict={s.expected_protected} />
                    {s.honest_note && (
                      <span className="mt-1 block text-sm text-ink-muted">Not stopped yet</span>
                    )}
                  </td>
                  <td className="py-4 pr-7 text-right">
                    <button
                      type="button"
                      disabled={start.isPending}
                      onClick={() => run(s.id)}
                      className="h-10 rounded-full border border-rule-strong px-5 text-sm font-medium transition-colors hover:bg-button hover:text-button-ink disabled:opacity-50"
                    >
                      Run
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {start.error && <Problem error={start.error} />}
    </>
  );
}

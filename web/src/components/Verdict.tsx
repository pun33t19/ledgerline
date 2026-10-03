import { controlName } from "../lib/controls";
import type { ModeView } from "../lib/runState";

interface Props {
  view: ModeView;
  running: boolean;
}

export function Verdict({ view, running }: Props) {
  const outcome = view.outcome;
  if (!outcome) {
    return (
      <div aria-live="polite" className="min-h-[5.5rem] py-3 text-ink-muted">
        {running ? "Running…" : "Waiting for the run to start"}
      </div>
    );
  }
  if (outcome.verdict === "harmed") {
    return (
      <div
        aria-live="polite"
        className="min-h-[5.5rem] rounded-sm border-l-4 border-loss bg-loss-wash px-4 py-3"
      >
        <p className="text-lg font-bold text-loss">The attacker got the secret</p>
        <ul className="mt-1 space-y-0.5 text-sm">
          {view.stolen.map((s) => (
            <li key={s.seq}>
              via <span className="font-mono">{s.via}</span>: <span className="font-mono">{s.data}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  const stoppedBy = outcome.stopped_by ?? [];
  return (
    <div
      aria-live="polite"
      className="min-h-[5.5rem] rounded-sm border-l-4 border-safe bg-safe-wash px-4 py-3"
    >
      <p className="text-lg font-bold text-safe">
        {stoppedBy.length > 0 ? "Stopped before any harm" : "No harm done"}
      </p>
      {stoppedBy.length > 0 && (
        <p className="mt-1 text-sm">Stopped by {stoppedBy.map(controlName).join(" and ")}.</p>
      )}
    </div>
  );
}

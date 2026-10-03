import type { Mode } from "../api/types";
import { controlName } from "../lib/controls";
import type { ModeView } from "../lib/runState";

interface Props {
  mode: Mode;
  view: ModeView;
  baseline: boolean;
}

/** The attack as a short sequence: launched, intercepted or not, outcome. */
export function AttackPath({ mode, view, baseline }: Props) {
  if (!view.outcome) return null;
  const controls = [...new Set(view.decisions.map((d) => controlName(d.control)))];
  const stolen = view.stolen.length > 0;
  const steps = [
    { label: baseline ? "Normal request" : "Attack launched", tone: "text-ink" },
    {
      label:
        mode === "unprotected"
          ? "Nothing in between"
          : controls.length > 0
            ? `${controls.join(" and ")} stepped in`
            : "Ledgerline did not need to step in",
      tone: controls.length > 0 ? "text-guard" : "text-ink-muted",
    },
    { label: stolen ? "Secret stolen" : "Secret safe", tone: stolen ? "text-loss" : "text-safe" },
  ];
  return (
    <ol className="my-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm" aria-label="Attack path">
      {steps.map((step, i) => (
        <li key={step.label} className="flex items-center gap-2">
          <span className={`${step.tone} ${i === 2 ? "font-bold" : ""}`}>
            {i + 1}. {step.label}
          </span>
          {i < steps.length - 1 && (
            <span aria-hidden="true" className="text-ink-muted">
              ›
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}

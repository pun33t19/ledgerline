import { controlName } from "../lib/controls";
import type { Entry } from "../lib/runState";

const NODE_NAMES = { host: "AI host", ledgerline: "Ledgerline", server: "Server" } as const;

/** Turn machine codes like `tool_changed` into words; leave free text (which may name tools) alone. */
export const humanize = (text: string): string =>
  /^[a-z]+(?:[_:][a-z]+)*$/.test(text) ? text.replaceAll(/[_:]/g, " ") : text;

export function entryLabel(entry: Entry): {
  who: string;
  what: string;
  tone: "ink" | "muted" | "guard" | "loss";
} {
  switch (entry.type) {
    case "step":
      return {
        who: "Agent",
        what: entry.status === "skipped" ? `${entry.title} (skipped)` : entry.title,
        tone: entry.status === "error" ? "loss" : "ink",
      };
    case "message":
      return {
        who: `${NODE_NAMES[entry.source]} to ${NODE_NAMES[entry.target]}${entry.internal ? ", Ledgerline's own check" : ""}`,
        what: entry.summary,
        tone: entry.internal ? "guard" : "muted",
      };
    case "decision":
      return {
        who: controlName(entry.control),
        what: `${entry.action === "replaced" ? "changed the reply" : entry.action}: ${humanize(entry.reason)}`,
        tone: "guard",
      };
    case "alert":
      return {
        who: "Alert",
        what: `${entry.event.replaceAll("_", " ")}${entry.tool ? ` on ${entry.tool}` : ""}`,
        tone: "guard",
      };
    case "exfiltration":
      return { who: "Attacker", what: `received ${entry.data} via ${entry.via}`, tone: "loss" };
  }
}

const TONE = { ink: "text-ink", muted: "text-ink-muted", guard: "text-guard", loss: "text-loss" };

interface Props {
  entries: Entry[];
  showMessages: boolean;
  onSelect: (entry: Entry) => void;
}

export function LedgerEntries({ entries, showMessages, onSelect }: Props) {
  const shown = showMessages ? entries : entries.filter((e) => e.type !== "message");
  if (shown.length === 0) return <p className="py-4 text-ink-muted">No entries yet.</p>;
  return (
    <ol className="ruled border-y border-rule" aria-label="Timeline">
      {shown.map((entry) => {
        const { who, what, tone } = entryLabel(entry);
        const strong = entry.type !== "message";
        return (
          <li key={entry.seq} className="ink-in">
            <button
              type="button"
              onClick={() => onSelect(entry)}
              className="grid w-full grid-cols-[3.75rem_1fr] gap-x-3 px-1 py-1.5 text-left hover:bg-paper-raised rounded-lg"
            >
              <span className="pt-0.5 text-right font-mono text-xs tabular-nums text-ink-muted">
                {(entry.t_ms / 1000).toFixed(2)}s
              </span>
              <span className="min-w-0">
                <span className={`block text-xs ${tone === "muted" ? "text-ink-muted" : TONE[tone]}`}>
                  {who}
                </span>
                <span
                  className={`block break-words ${entry.type === "message" ? "font-mono text-[13px]" : ""} ${strong ? TONE[tone] : "text-ink"} ${entry.type === "decision" || entry.type === "exfiltration" ? "font-medium" : ""}`}
                >
                  {what}
                </span>
                {entry.type === "step" && entry.detail && (
                  <span className="block text-sm text-ink-muted">{entry.detail}</span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

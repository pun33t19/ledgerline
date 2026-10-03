import type { MessageEvent, Mode } from "../api/types";
import type { ModeView } from "../lib/runState";

const X = { host: 40, ledgerline: 160, server: 280 } as const;
const Y = 34;

interface Props {
  mode: Mode;
  view: ModeView;
}

function Node({ x, label, tone }: { x: number; label: string; tone: "ink" | "guard" | "loss" }) {
  const stroke = tone === "guard" ? "stroke-guard" : tone === "loss" ? "stroke-loss" : "stroke-rule-strong";
  const text = tone === "guard" ? "fill-guard" : tone === "loss" ? "fill-loss" : "fill-ink";
  return (
    <g>
      <rect
        x={x - 34}
        y={Y - 14}
        width={68}
        height={28}
        rx={4}
        className={`fill-paper-raised ${stroke}`}
        strokeWidth={1.5}
      />
      <text x={x} y={Y + 4.5} textAnchor="middle" className={`${text} text-[11px] font-bold`}>
        {label}
      </text>
    </g>
  );
}

function Packet({ message }: { message: MessageEvent }) {
  const from = X[message.source];
  const to = X[message.target];
  const reduced =
    typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const fill = message.internal ? "fill-guard" : message.kind === "response" ? "fill-ink-muted" : "fill-ink";
  if (reduced) return <circle cx={to} cy={Y - 20} r={3.5} className={fill} />;
  return (
    <circle r={3.5} className={fill}>
      <animateMotion dur="0.5s" fill="freeze" path={`M${from} ${Y - 20} L${to} ${Y - 20}`} />
    </circle>
  );
}

export function FlowStrip({ mode, view }: Props) {
  const stoppedHere = view.decisions.length;
  const leaked = view.stolen.length > 0;
  return (
    <figure className="my-3">
      <svg
        viewBox="0 0 320 72"
        className="h-auto w-full max-w-md"
        role="img"
        aria-label={
          mode === "protected"
            ? "Messages flow from the AI host through Ledgerline to the server"
            : "Messages flow from the AI host straight to the server"
        }
      >
        <line x1={X.host} y1={Y} x2={X.server} y2={Y} className="stroke-rule-strong" strokeWidth={1.5} />
        <Node x={X.host} label="AI host" tone="ink" />
        {mode === "protected" && <Node x={X.ledgerline} label="Ledgerline" tone="guard" />}
        <Node x={X.server} label="Server" tone={leaked ? "loss" : "ink"} />
        {view.lastMessage && <Packet key={view.lastMessage.seq} message={view.lastMessage} />}
        {mode === "protected" && stoppedHere > 0 && (
          <text x={X.ledgerline} y={Y + 30} textAnchor="middle" className="fill-guard text-[10px]">
            stepped in {stoppedHere === 1 ? "once" : `${stoppedHere} times`}
          </text>
        )}
        {leaked && (
          <text x={X.server} y={Y + 30} textAnchor="middle" className="fill-loss text-[10px]">
            secret leaked
          </text>
        )}
      </svg>
    </figure>
  );
}

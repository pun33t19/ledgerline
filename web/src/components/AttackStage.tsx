import {
  type CSSProperties,
  type PointerEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { Mode } from "../api/types";
import type { Beat, NodeId, Tone } from "../lib/story";

// The world is laid out on a fixed 1000×560 floor and scaled to fit; the floor is tilted in 3D.
const W = 1000;
const H = 560;
const AT: Record<NodeId, { x: number; y: number }> = {
  agent: { x: 170, y: 330 },
  ledgerline: { x: 500, y: 330 },
  server: { x: 830, y: 330 },
  secrets: { x: 330, y: 515 },
  attacker: { x: 860, y: 105 },
};
const BEAT_MS = 2600;

const TONE_TEXT: Record<Tone, string> = {
  normal: "text-ink",
  attack: "text-loss",
  leak: "text-loss",
  blocked: "text-guard",
  safe: "text-safe",
};
const TONE_FILL: Record<Tone, string> = {
  normal: "var(--ink)",
  attack: "var(--loss)",
  leak: "var(--loss)",
  blocked: "var(--guard)",
  safe: "var(--safe)",
};

/** The packet's route: on the protected side, everything between agent and server passes Ledgerline. */
function route(beat: Beat, mode: Mode): NodeId[] {
  if (!beat.from || !beat.to) return [];
  const endpoints = new Set([beat.from, beat.to]);
  const crossesProxy = mode === "protected" && endpoints.has("agent") && endpoints.has("server");
  if (!crossesProxy) return [beat.from, beat.to];
  return beat.halted ? [beat.from, "ledgerline"] : [beat.from, "ledgerline", beat.to];
}

const pathOf = (nodes: NodeId[]) => nodes.map((n, i) => `${i ? "L" : "M"}${AT[n].x} ${AT[n].y}`).join(" ");

function Icon({ node }: { node: NodeId }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
      {node === "agent" && (
        <g {...common}>
          <rect x="5" y="7" width="14" height="11" rx="3" />
          <path d="M12 3v4M9 12h.01M15 12h.01M9.5 15h5" />
        </g>
      )}
      {node === "ledgerline" && (
        <g {...common}>
          <path d="M4 7h16M4 12h16M4 17h16" opacity="0.45" />
          <path d="M10.5 4v16M13.5 4v16" />
        </g>
      )}
      {node === "server" && (
        <g {...common}>
          <rect x="4" y="4" width="16" height="6" rx="1.5" />
          <rect x="4" y="14" width="16" height="6" rx="1.5" />
          <path d="M8 7h.01M8 17h.01" />
        </g>
      )}
      {node === "secrets" && (
        <g {...common}>
          <circle cx="8" cy="12" r="3.5" />
          <path d="M11.5 12H20M17 12v3M20 12v2" />
        </g>
      )}
      {node === "attacker" && (
        <g {...common}>
          <path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z" />
          <circle cx="12" cy="12" r="2.5" />
        </g>
      )}
    </svg>
  );
}

const LABEL: Record<NodeId, string> = {
  agent: "Your AI agent",
  ledgerline: "Ledgerline",
  server: "Tool server",
  secrets: "Your secrets",
  attacker: "Attacker",
};

interface NodeState {
  status?: string;
  tone?: Tone;
  dim?: boolean;
}

function StageNode({ id, state, focused }: { id: NodeId; state: NodeState; focused?: Tone }) {
  const ring = focused ? TONE_FILL[focused] : undefined;
  const border =
    state.tone === "leak" || state.tone === "attack"
      ? "border-loss/60"
      : state.tone === "blocked"
        ? "border-guard/60"
        : state.tone === "safe"
          ? "border-safe/50"
          : "border-rule-strong";
  return (
    <div className="stage-node" style={{ left: AT[id].x, top: AT[id].y }}>
      <div
        className={`glass relative flex ${ring ? "node-pulse" : ""} min-w-[9.5rem] items-center gap-2.5 rounded-2xl px-3.5 py-2.5 shadow-[0_18px_40px_-18px_rgb(0_0_0/0.55)] transition-opacity duration-500 ${border} ${state.dim ? "opacity-35" : ""}`}
        style={{ background: "var(--glass-strong)", ...(ring ? { "--pulse": ring } : {}) } as CSSProperties}
      >
        <span
          className={id === "ledgerline" ? "text-guard" : state.tone ? TONE_TEXT[state.tone] : "text-ink"}
        >
          <Icon node={id} />
        </span>
        <span className="leading-tight">
          <span className="block text-[15px] font-medium">{LABEL[id]}</span>
          <span className={`block text-xs ${state.tone ? TONE_TEXT[state.tone] : "text-ink-muted"}`}>
            {state.status ?? " "}
          </span>
        </span>
      </div>
    </div>
  );
}

/** What each node looks like after the beats played so far. */
function nodeStates(mode: Mode, beats: Beat[], upTo: number): Record<NodeId, NodeState> {
  const seen = beats.slice(0, upTo + 1);
  const leaked = seen.some((b) => b.focus === "attacker" && b.tone === "leak");
  const read = seen.some((b) => b.to === "secrets");
  const blocks = seen.filter((b) => b.tone === "blocked").length;
  const poisoned = seen.some((b) => b.from === "server" && b.to === "agent" && b.tone === "attack");
  const finished = seen.at(-1)?.id === `${mode}-outcome`;
  return {
    agent: poisoned
      ? { status: "fooled by the tool list", tone: "attack" }
      : { status: "following instructions" },
    ledgerline:
      blocks > 0
        ? { status: blocks === 1 ? "stepped in once" : `stepped in ${blocks} times`, tone: "blocked" }
        : { status: "checking every message" },
    server: { status: "third-party code" },
    secrets: read
      ? { status: "read", tone: "attack" }
      : finished
        ? { status: "untouched", tone: "safe" }
        : {},
    attacker: leaked ? { status: "has your secret", tone: "leak" } : { status: "waiting", dim: true },
  };
}

interface WorldProps {
  mode: Mode;
  beats: Beat[];
  index: number;
  scale: number;
  dragging?: boolean;
  reduced?: boolean;
}

/** The tilted floor with its nodes, edges and the moving packet for one beat. */
export function StageWorld({ mode, beats, index, scale, dragging = false, reduced = false }: WorldProps) {
  const beat = beats[Math.min(index, Math.max(beats.length - 1, 0))];
  const states = nodeStates(mode, beats, index);
  const path = beat ? route(beat, mode) : [];
  const nodes: NodeId[] =
    mode === "protected"
      ? ["agent", "ledgerline", "server", "secrets", "attacker"]
      : ["agent", "server", "secrets", "attacker"];
  const usesServerSecrets = beats.some((b) => b.from === "server" && b.to === "secrets");
  return (
    <div
      className="absolute top-1/2 left-1/2"
      style={{
        width: W,
        height: H,
        transform: `translate(-50%, -50%) scale(${scale})`,
        transformOrigin: "50% 50%",
      }}
    >
      <div className="stage-plane" data-dragging={dragging} />
      <div className="stage-graph" data-dragging={dragging}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="absolute inset-0 h-full w-full overflow-visible"
          aria-hidden="true"
        >
          <g fill="none" strokeWidth={2} strokeLinecap="round" stroke="var(--rule-strong)">
            <path d={pathOf(["agent", "server"])} />
            <path d={pathOf(["agent", "secrets"])} />
            <path d={pathOf(["server", "attacker"])} strokeDasharray="2 7" />
            {usesServerSecrets && <path d={pathOf(["server", "secrets"])} strokeDasharray="2 7" />}
          </g>
          {mode === "unprotected" && (
            <g>
              <circle
                cx={AT.ledgerline.x}
                cy={AT.ledgerline.y}
                r={34}
                fill="none"
                stroke="var(--rule-strong)"
                strokeDasharray="4 6"
              />
              <text
                x={AT.ledgerline.x}
                y={AT.ledgerline.y + 62}
                textAnchor="middle"
                className="fill-ink-muted text-[17px]"
              >
                nothing in between
              </text>
            </g>
          )}
          {path.length > 1 && beat && (
            <path
              key={`edge-${beat.id}`}
              d={pathOf(path)}
              fill="none"
              stroke={TONE_FILL[beat.tone]}
              strokeWidth={3}
              strokeLinecap="round"
              className="edge-live"
              opacity={0.85}
            />
          )}
          {beat?.halted && (
            <g key={`stop-${beat.id}`} transform={`translate(${AT.ledgerline.x - 80} ${AT.ledgerline.y})`}>
              <circle r={17} fill="var(--paper)" stroke="var(--guard)" strokeWidth={2.5} />
              <path d="M-7 -7L7 7" stroke="var(--guard)" strokeWidth={2.5} strokeLinecap="round" />
            </g>
          )}
        </svg>

        {path.length > 1 && beat && !reduced && (
          <span
            key={`packet-${beat.id}`}
            aria-hidden="true"
            className="packet absolute top-0 left-0 block h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full"
            style={{
              offsetPath: `path("${pathOf(path)}")`,
              background: TONE_FILL[beat.tone],
              boxShadow: `0 0 0 6px color-mix(in srgb, ${TONE_FILL[beat.tone]} 22%, transparent), 0 0 28px 6px color-mix(in srgb, ${TONE_FILL[beat.tone]} 45%, transparent)`,
              animationDuration: `${Math.min(1.6, 0.7 * (path.length - 1) + 0.4)}s`,
            }}
          />
        )}

        {nodes.map((id) => (
          <StageNode
            key={id}
            id={id}
            state={states[id]}
            focused={beat && beat.focus === id ? beat.tone : undefined}
          />
        ))}
      </div>
    </div>
  );
}

interface Props {
  mode: Mode;
  beats: Beat[];
  running: boolean;
  onFinished?: () => void;
}

export function AttackStage({ mode, beats, running, onFinished }: Props) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [flat, setFlat] = useState(false);
  const [spin, setSpin] = useState(-8);
  const [tilt, setTilt] = useState(50);
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ x: number; y: number; spin: number; tilt: number } | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const reduced = useMemo(
    () =>
      typeof window !== "undefined" &&
      (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false),
    [],
  );

  // Fit the fixed-size world to the available width.
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    // Phones crop the floor's empty margins a little so the nodes stay legible.
    const resize = () => setScale(Math.min(1.15, el.clientWidth / (el.clientWidth < 640 ? 860 : W)));
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const last = beats.length - 1;
  const atEnd = index >= last;
  const done = atEnd && !running;

  // Advance one beat at a time while playing; wait at the end for more beats if the run is live.
  useEffect(() => {
    if (!playing || beats.length === 0 || index >= last) return;
    const timer = window.setTimeout(() => setIndex((i) => Math.min(i + 1, last)), BEAT_MS);
    return () => window.clearTimeout(timer);
  }, [playing, index, last, beats.length]);

  const reported = useRef(false);
  useEffect(() => {
    if (done && beats.length > 0 && !reported.current) {
      reported.current = true;
      onFinished?.();
    }
    if (!done) reported.current = false;
  }, [done, beats.length, onFinished]);

  const beat = beats[Math.min(index, Math.max(last, 0))];

  const onPointerDown = (e: PointerEvent) => {
    if (flat) return;
    drag.current = { x: e.clientX, y: e.clientY, spin, tilt };
    setDragging(true);
    (e.target as Element).setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: PointerEvent) => {
    if (!drag.current) return;
    const dx = e.clientX - drag.current.x;
    const dy = e.clientY - drag.current.y;
    setSpin(Math.max(-40, Math.min(40, drag.current.spin + dx / 6)));
    setTilt(Math.max(28, Math.min(64, drag.current.tilt - dy / 6)));
  };
  const endDrag = () => {
    drag.current = null;
    setDragging(false);
  };

  const vars = {
    "--tilt": `${flat ? 0 : tilt}deg`,
    "--spin": `${flat ? 0 : spin}deg`,
  } as CSSProperties;
  const height = H * scale * (flat ? 1 : 0.8);

  return (
    <div>
      <div
        ref={box}
        className="stage relative overflow-hidden select-none"
        style={{
          ...vars,
          height,
          cursor: flat ? "default" : dragging ? "grabbing" : "grab",
          touchAction: "pan-y",
        }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        role="img"
        aria-label={`Attack map ${mode === "protected" ? "with" : "without"} Ledgerline. ${beat?.title ?? ""}`}
      >
        <StageWorld
          mode={mode}
          beats={beats}
          index={index}
          scale={scale}
          dragging={dragging}
          reduced={reduced}
        />
      </div>

      {/* Caption + player */}
      <div className="mt-2 grid gap-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <div aria-live="polite" className="min-h-[6.5rem] max-w-[46rem]">
          {beat ? (
            <div key={beat.id} className="caption-in">
              <p className="text-sm text-ink-muted">
                Step {Math.min(index, last) + 1} of {beats.length}
                {running && " (live)"}
              </p>
              <p className={`display mt-1 text-[1.75rem] md:text-[2.1rem] ${TONE_TEXT[beat.tone]}`}>
                {beat.title}
              </p>
              {beat.detail && <p className="mt-2 max-w-[38rem] break-words text-ink-muted">{beat.detail}</p>}
            </div>
          ) : (
            <p className="display text-[1.75rem] text-ink-muted">
              {running ? "Starting the attack…" : "Waiting for the run"}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PlayerButton
            label="Restart"
            onClick={() => {
              setIndex(0);
              setPlaying(true);
            }}
            disabled={beats.length === 0}
          >
            <path d="M4 5v5h5M4.6 10A8 8 0 1 1 6 16" />
          </PlayerButton>
          <PlayerButton
            label="Previous step"
            onClick={() => {
              setPlaying(false);
              setIndex((i) => Math.max(0, i - 1));
            }}
            disabled={index === 0}
          >
            <path d="M15 5l-7 7 7 7" />
          </PlayerButton>
          <button
            type="button"
            onClick={() => {
              if (atEnd) {
                setIndex(0);
                setPlaying(true);
              } else setPlaying((p) => !p);
            }}
            disabled={beats.length === 0}
            className="inline-flex h-11 min-w-[7.5rem] items-center justify-center gap-2 rounded-full bg-button px-5 font-medium text-button-ink disabled:opacity-40"
          >
            {atEnd && !running ? "Replay" : playing ? "Pause" : "Play"}
          </button>
          <PlayerButton
            label="Next step"
            onClick={() => {
              setPlaying(false);
              setIndex((i) => Math.min(last, i + 1));
            }}
            disabled={atEnd}
          >
            <path d="M9 5l7 7-7 7" />
          </PlayerButton>
          <button
            type="button"
            aria-pressed={!flat}
            onClick={() => setFlat((f) => !f)}
            className="h-11 rounded-full border border-rule-strong px-4 text-sm text-ink-muted hover:text-ink"
          >
            {flat ? "3D view" : "Flat view"}
          </button>
        </div>
      </div>

      {/* The beats as a scrubbable sequence */}
      <ol className="mt-5 flex gap-1.5" aria-label="Steps of the attack">
        {beats.map((b, i) => (
          <li key={b.id} className="min-w-0 flex-1">
            <button
              type="button"
              onClick={() => {
                setPlaying(false);
                setIndex(i);
              }}
              aria-current={i === index ? "step" : undefined}
              aria-label={`Step ${i + 1}: ${b.title}`}
              className="group block w-full py-2"
            >
              <span
                className="block h-1 rounded-full transition-colors"
                style={{
                  background: i <= index ? TONE_FILL[b.tone] : "var(--rule-strong)",
                  opacity: i === index ? 1 : i < index ? 0.55 : 1,
                }}
              />
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

function PlayerButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-rule-strong text-ink hover:bg-paper-raised disabled:opacity-35"
    >
      <svg
        viewBox="0 0 24 24"
        className="h-4 w-4"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        {children}
      </svg>
    </button>
  );
}

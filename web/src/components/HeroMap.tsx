import { type CSSProperties, useEffect, useRef, useState } from "react";
import type { Mode } from "../api/types";
import { usePrefersReducedMotion } from "../lib/motion";
import type { Beat } from "../lib/story";
import { StageWorld } from "./AttackStage";

// A short, looping illustration for the landing page: the same attack without and with Ledgerline.
const LOOP: { mode: Mode; beats: Beat[] }[] = [
  {
    mode: "unprotected",
    beats: [
      { id: "u1", from: "agent", to: "server", focus: "server", tone: "normal", title: "" },
      { id: "u2", from: "server", to: "agent", focus: "agent", tone: "attack", title: "" },
      { id: "u3", from: "agent", to: "secrets", focus: "secrets", tone: "attack", title: "" },
      { id: "u4", from: "agent", to: "server", focus: "server", tone: "leak", title: "" },
      { id: "u5", from: "server", to: "attacker", focus: "attacker", tone: "leak", title: "" },
    ],
  },
  {
    mode: "protected",
    beats: [
      { id: "p1", from: "agent", to: "server", focus: "server", tone: "normal", title: "" },
      { id: "p2", from: "server", to: "ledgerline", focus: "ledgerline", tone: "blocked", title: "" },
      {
        id: "p3",
        from: "agent",
        to: "server",
        halted: true,
        focus: "ledgerline",
        tone: "blocked",
        title: "",
      },
      { id: "p4", focus: "secrets", tone: "safe", title: "" },
    ],
  },
];
const STEP_MS = 1900;

export function HeroMap() {
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0.8);
  const [tick, setTick] = useState(0);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const resize = () => setScale(el.clientWidth / 1000);
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (reduced) return;
    const timer = window.setInterval(() => setTick((t) => t + 1), STEP_MS);
    return () => window.clearInterval(timer);
  }, [reduced]);

  // Walk through both stories in turn, pausing on each one's last beat.
  const total = LOOP.reduce((n, s) => n + s.beats.length + 1, 0);
  let t = reduced ? (LOOP[0]?.beats.length ?? 0) : tick % total;
  let scene = LOOP[0];
  for (const s of LOOP) {
    if (t <= s.beats.length) {
      scene = s;
      break;
    }
    t -= s.beats.length + 1;
  }
  if (!scene) return null;

  return (
    <div
      ref={box}
      aria-hidden="true"
      className="stage pointer-events-none absolute inset-0"
      style={{ "--tilt": "50deg", "--spin": "-10deg" } as CSSProperties}
    >
      <StageWorld
        key={scene.mode}
        mode={scene.mode}
        beats={scene.beats}
        index={Math.min(t, scene.beats.length - 1)}
        scale={scale}
        reduced={reduced}
      />
    </div>
  );
}

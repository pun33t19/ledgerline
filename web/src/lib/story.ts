// Turns one side of a run into a short story the attack stage can play back, beat by beat.
// Pure and derived only from the run's events, so what the stage shows is what actually happened.
import type { Decision, Exfiltration, Mode, Step } from "../api/types";
import { controlName } from "./controls";
import type { ModeView } from "./runState";

export type NodeId = "agent" | "ledgerline" | "server" | "secrets" | "attacker";
export type Tone = "normal" | "attack" | "blocked" | "leak" | "safe";

export interface Beat {
  id: string;
  /** Where the packet travels; the stage routes agent↔server through Ledgerline on the protected side. */
  from?: NodeId;
  to?: NodeId;
  /** The packet stops at Ledgerline instead of reaching `to`. */
  halted?: boolean;
  /** The node the beat is about (glows). */
  focus: NodeId;
  tone: Tone;
  title: string;
  detail?: string;
}

const OBEY = /^call (\S+) \(obeying hidden instructions: added ([^)]+)\)$/;
const CALL = /^call (\S+)/;
const HIDDEN = /<IMPORTANT>/;

const sentence = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1);

/** Why a control stepped in, in words a non-specialist can follow. */
const WHY: Record<string, string> = {
  "tool-pinning": "Its definition no longer matches the version you approved.",
  "verify-before-call":
    "Just before forwarding, Ledgerline re-read the tool's definition from the server. It no longer matches the version you approved.",
  "strict-parsing":
    "The message had the same key twice, so Ledgerline and the server could read it differently.",
};
const why = (d: Decision): string => WHY[d.control] ?? d.reason;

/** Steps carry the agent's view; decisions and alerts arrive just before the step they affected,
 * exfiltrations just after. Group them that way. */
interface Group {
  step: Step;
  decisions: Decision[];
  stolen: Exfiltration[];
}

function groups(view: ModeView): Group[] {
  const out: Group[] = [];
  let decisions: Decision[] = [];
  for (const entry of view.entries) {
    if (entry.type === "decision") decisions.push(entry);
    else if (entry.type === "step") {
      out.push({ step: entry, decisions, stolen: [] });
      decisions = [];
    } else if (entry.type === "exfiltration") out.at(-1)?.stolen.push(entry);
  }
  return out;
}

function stolenBeats(id: string, stolen: Exfiltration[]): Beat[] {
  return stolen.flatMap((s, i): Beat[] => {
    const beats: Beat[] = [];
    if (s.via === "server-side") {
      beats.push({
        id: `${id}-read-${i}`,
        from: "server",
        to: "secrets",
        focus: "secrets",
        tone: "attack",
        title: "The tool server's own code reads your secrets file. No model was involved.",
      });
    }
    beats.push({
      id: `${id}-leak-${i}`,
      from: "server",
      to: "attacker",
      focus: "attacker",
      tone: "leak",
      title: "The attacker now has your secret.",
      detail: s.data,
    });
    return beats;
  });
}

export function buildStory(mode: Mode, view: ModeView): Beat[] {
  const beats: Beat[] = [];
  const menus = [...view.menus];
  // Repeated, uneventful calls to the same tool become one beat.
  const quiet: { call: { id: string; tool: string; count: number } | null } = { call: null };

  const flushQuiet = () => {
    if (!quiet.call) return;
    const { id, tool, count } = quiet.call;
    beats.push({
      id,
      from: "agent",
      to: "server",
      focus: "server",
      tone: "normal",
      title:
        count === 1
          ? `Your agent calls ${tool}. Everything looks normal.`
          : `Your agent calls ${tool} ${count} times. Everything looks normal.`,
    });
    quiet.call = null;
  };

  for (const { step, decisions, stolen } of groups(view)) {
    const id = `${mode}-${step.index}`;
    const title = step.title;
    const blocked = decisions.find((d) => d.action === "blocked" || d.action === "rejected");
    const hid = decisions.find((d) => d.action === "replaced");
    const plain = CALL.exec(title);
    const isQuiet = plain && !OBEY.test(title) && step.status === "done" && !blocked && stolen.length === 0;

    if (isQuiet && plain) {
      const call = quiet.call;
      if (call && call.tool === plain[1]) call.count += 1;
      else {
        flushQuiet();
        quiet.call = { id, tool: plain[1] ?? "", count: 1 };
      }
      continue;
    }
    flushQuiet();

    if (title.startsWith("connect")) {
      beats.push({
        id,
        from: "agent",
        to: "server",
        focus: "server",
        tone: "normal",
        title: "Your agent connects to a tool server.",
        detail: step.detail,
      });
    } else if (title === "list tools") {
      const menu = menus.shift();
      if (hid) {
        beats.push({
          id: `${id}-hide`,
          from: "server",
          to: "ledgerline",
          focus: "ledgerline",
          tone: "blocked",
          title: `Ledgerline spots a tool that changed since you approved it and hides it from your agent.`,
          detail: why(hid),
        });
      }
      const poisoned = menu?.tools.find((t) => HIDDEN.test(t.description));
      beats.push(
        poisoned
          ? {
              id,
              from: "server",
              to: "agent",
              focus: "agent",
              tone: "attack",
              title: `The tool list hides instructions for the model inside ${poisoned.name}'s description. You never see them; your agent does.`,
            }
          : {
              id,
              from: "server",
              to: "agent",
              focus: "agent",
              tone: hid ? "safe" : "normal",
              title: hid
                ? "Your agent only sees the tools you approved."
                : `The server sends its tool list: ${step.detail || "no tools"}.`,
            },
      );
    } else if (step.status === "skipped") {
      beats.push({
        id,
        focus: "agent",
        tone: "safe",
        title: sentence(`${step.detail}. Your agent moves on.`),
      });
    } else {
      const obey = OBEY.exec(title);
      if (obey) {
        beats.push({
          id: `${id}-read`,
          from: "agent",
          to: "secrets",
          focus: "secrets",
          tone: "attack",
          title: "Following those hidden instructions, your agent reads your secrets file.",
        });
      }
      const tool = obey?.[1] ?? plain?.[1];
      beats.push({
        id,
        from: "agent",
        to: "server",
        halted: Boolean(blocked),
        focus: blocked ? "ledgerline" : "server",
        tone: blocked ? "blocked" : obey ? "leak" : "attack",
        title: blocked
          ? `Ledgerline stops the ${tool ? `call to ${tool}` : "message"} before the server sees it.`
          : obey
            ? `Your agent calls ${tool}, with the secret tucked into the "${obey[2]}" argument.`
            : tool
              ? `Your agent calls ${tool} as usual.`
              : /two `arguments`/.test(title)
                ? "A crafted call arrives with two `arguments` keys: a harmless copy, and one carrying your secret."
                : sentence(`${title}.`),
        detail: blocked ? why(blocked) : undefined,
      });
    }
    beats.push(...stolenBeats(id, stolen));
  }
  flushQuiet();

  const outcome = view.outcome;
  if (outcome) {
    const stoppedBy = outcome.stopped_by ?? [];
    beats.push(
      outcome.verdict === "harmed"
        ? {
            id: `${mode}-outcome`,
            focus: "attacker",
            tone: "leak",
            title:
              mode === "unprotected"
                ? "Compromised. Nothing stood between your agent and the tool server."
                : "Compromised. None of Ledgerline's current controls catch this attack.",
          }
        : {
            id: `${mode}-outcome`,
            focus: stoppedBy.length > 0 ? "ledgerline" : "secrets",
            tone: "safe",
            title:
              stoppedBy.length > 0
                ? `Your secret never left. Stopped by ${stoppedBy.map(controlName).join(" and ")}.`
                : "Nothing harmful happened.",
          },
    );
  }
  return beats;
}

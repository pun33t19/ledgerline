// Turns the stream of run events into what each ledger column shows. Pure: easy to test.
import type {
  Alert,
  Controls,
  Decision,
  Exfiltration,
  Menu,
  MessageEvent,
  Mode,
  Outcome,
  RunEvent,
  Step,
  ToolDef,
} from "../api/types";

export type Entry = Step | MessageEvent | Decision | Alert | Exfiltration;

export interface ModeView {
  entries: Entry[];
  outcome?: Outcome;
  menus: Menu[];
  lastMessage?: MessageEvent;
  decisions: Decision[];
  stolen: Exfiltration[];
}

export interface RunView {
  status: "connecting" | "running" | "finished" | "failed";
  runId?: string;
  scenarioId?: string;
  controls?: Controls;
  pinned?: ToolDef[];
  error?: string | null;
  modes: Record<Mode, ModeView>;
}

const emptyMode = (): ModeView => ({ entries: [], menus: [], decisions: [], stolen: [] });

export const initialRun = (): RunView => ({
  status: "connecting",
  modes: { unprotected: emptyMode(), protected: emptyMode() },
});

function updateMode(view: RunView, mode: Mode, change: (m: ModeView) => ModeView): RunView {
  return { ...view, modes: { ...view.modes, [mode]: change(view.modes[mode]) } };
}

export function applyEvent(view: RunView, event: RunEvent): RunView {
  switch (event.type) {
    case "run_started":
      return {
        ...view,
        status: "running",
        runId: event.run_id,
        scenarioId: event.scenario_id,
        controls: event.controls,
      };
    case "pinned":
      return { ...view, pinned: event.tools };
    case "run_finished":
      return { ...view, status: event.status, error: event.error ?? null };
    case "outcome":
      return updateMode(view, event.mode, (m) => ({ ...m, outcome: event }));
    case "menu":
      return updateMode(view, event.mode, (m) => ({ ...m, menus: [...m.menus, event] }));
    case "message":
      return updateMode(view, event.mode, (m) => ({
        ...m,
        entries: [...m.entries, event],
        lastMessage: event,
      }));
    case "decision":
      return updateMode(view, event.mode, (m) => ({
        ...m,
        entries: [...m.entries, event],
        decisions: [...m.decisions, event],
      }));
    case "exfiltration":
      return updateMode(view, event.mode, (m) => ({
        ...m,
        entries: [...m.entries, event],
        stolen: [...m.stolen, event],
      }));
    case "step":
    case "alert":
      return updateMode(view, event.mode, (m) => ({ ...m, entries: [...m.entries, event] }));
  }
}

/** The latest tool menu a mode's agent saw (what the model reads). */
export function latestMenu(mode: ModeView): ToolDef[] {
  return mode.menus.at(-1)?.tools ?? [];
}

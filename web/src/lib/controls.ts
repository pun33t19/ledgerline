// Plain-language names and explanations for Ledgerline's controls.
import type { Controls } from "../api/types";

export type ControlKey = keyof Controls;

export const CONTROLS: { key: ControlKey; id: string; name: string; explain: string }[] = [
  {
    key: "pinning",
    id: "tool-pinning",
    name: "Tool pinning",
    explain:
      "Compares every tool with the version you approved. Changed or unreviewed tools are hidden from the model and their calls are blocked.",
  },
  {
    key: "verify_each_call",
    id: "verify-before-call",
    name: "Check before every call",
    explain:
      "Before forwarding a tool call, asks the server for that tool's current definition and blocks the call if it no longer matches.",
  },
  {
    key: "strict_parsing",
    id: "strict-parsing",
    name: "Strict message parsing",
    explain:
      "Rejects ambiguous messages, such as JSON with the same key twice, that Ledgerline and the server could read differently.",
  },
];

export const controlName = (id: string): string =>
  CONTROLS.find((c) => c.id === id || c.key === id)?.name ?? id;

export const ALL_ON: Controls = { pinning: true, verify_each_call: true, strict_parsing: true };

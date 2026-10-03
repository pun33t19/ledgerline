// Friendly names for the types generated from the Python API (schema.d.ts). Never edit those by hand.
import type { components } from "./schema";

type S = components["schemas"];
export type ScenarioInfo = S["ScenarioInfo"];
export type Controls = S["Controls"];
export type RunSummary = S["RunSummary"];
export type RunRecord = S["RunRecord"];
export type Coverage = S["Coverage"];
export type CoverageRow = S["CoverageRow"];
export type ToolDef = S["ToolDef"];
export type Outcome = S["Outcome"];
export type Verdict = Outcome["verdict"];
export type Mode = Outcome["mode"];

export type RunStarted = S["RunStarted"];
export type Pinned = S["Pinned"];
export type Step = S["Step"];
export type MessageEvent = S["MessageEvent"];
export type Decision = S["Decision"];
export type Alert = S["Alert"];
export type Menu = S["Menu"];
export type Exfiltration = S["Exfiltration"];
export type RunFinished = S["RunFinished"];

export type RunEvent =
  | RunStarted
  | Pinned
  | Step
  | MessageEvent
  | Decision
  | Alert
  | Menu
  | Exfiltration
  | Outcome
  | RunFinished;

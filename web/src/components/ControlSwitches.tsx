import * as Switch from "@radix-ui/react-switch";
import type { Controls } from "../api/types";
import { CONTROLS } from "../lib/controls";

interface Props {
  value: Controls;
  onChange: (value: Controls) => void;
  relevant?: string[];
}

export function ControlSwitches({ value, onChange, relevant = [] }: Props) {
  return (
    <fieldset>
      <legend className="display mb-4 text-[1.7rem]">Ledgerline's controls</legend>
      <ul className="space-y-4">
        {CONTROLS.map((control) => {
          const id = `control-${control.key}`;
          const matters = relevant.includes(control.key);
          return (
            <li key={control.key} className="flex gap-3">
              <Switch.Root
                id={id}
                checked={value[control.key] ?? true}
                onCheckedChange={(checked) => onChange({ ...value, [control.key]: checked })}
                className="relative mt-0.5 h-6 w-10 shrink-0 rounded-full border border-rule-strong bg-paper-raised transition-colors data-[state=checked]:border-transparent data-[state=checked]:bg-button"
              >
                <Switch.Thumb className="block h-4 w-4 translate-x-1 rounded-full bg-ink-muted transition-transform data-[state=checked]:translate-x-[1.15rem] data-[state=checked]:bg-button-ink" />
              </Switch.Root>
              <label htmlFor={id} className="max-w-prose cursor-pointer">
                <span className="font-medium">{control.name}</span>
                {matters && <span className="ml-2 text-sm text-guard">matters here</span>}
                <span className="block text-sm text-ink-muted">{control.explain}</span>
              </label>
            </li>
          );
        })}
      </ul>
    </fieldset>
  );
}

import { useState } from "react";
import { setTheme, storedTheme, type ThemeChoice } from "../lib/theme";

const OPTIONS: { value: ThemeChoice; label: string; icon: string }[] = [
  {
    value: "light",
    label: "Light",
    icon: "M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  },
  { value: "dark", label: "Dark", icon: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" },
  { value: "system", label: "System", icon: "M4 5h16v11H4zM9 20h6M12 16v4" },
];

/** Light, dark, or follow the operating system. */
export function ThemeSwitch() {
  const [choice, setChoice] = useState<ThemeChoice>(storedTheme);
  return (
    <div role="radiogroup" aria-label="Theme" className="glass flex rounded-full p-1">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={choice === o.value}
          aria-label={`${o.label} theme`}
          title={`${o.label} theme`}
          onClick={() => {
            setTheme(o.value);
            setChoice(o.value);
          }}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full text-ink-muted transition-colors hover:text-ink aria-checked:bg-button aria-checked:text-button-ink"
        >
          <svg
            viewBox="0 0 24 24"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.7}
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d={o.icon} />
          </svg>
        </button>
      ))}
    </div>
  );
}

// Theme: light, dark, or follow the system. The choice is remembered; "system" tracks OS changes live.
export type ThemeChoice = "light" | "dark" | "system";
const KEY = "ledgerline-theme";

const media = (): MediaQueryList | undefined => window.matchMedia?.("(prefers-color-scheme: dark)");

export function storedTheme(): ThemeChoice {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

function apply(choice: ThemeChoice): void {
  const dark = choice === "dark" || (choice === "system" && (media()?.matches ?? false));
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

export function setTheme(choice: ThemeChoice): void {
  apply(choice);
  try {
    if (choice === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, choice);
  } catch {
    // storage can be unavailable (private mode); the theme still applies for this visit
  }
}

export function initTheme(): void {
  apply(storedTheme());
  media()?.addEventListener("change", () => {
    if (storedTheme() === "system") apply("system");
  });
}

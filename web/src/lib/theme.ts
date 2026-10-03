// Light/dark theme: follows the system until the person picks one, then remembers it.
export type Theme = "light" | "dark";
const KEY = "ledgerline-theme";

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    // storage can be unavailable (private mode); the theme still applies for this visit
  }
}

export function initTheme(): void {
  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  document.documentElement.dataset.theme = stored() ?? (prefersDark ? "dark" : "light");
}

import { useState } from "react";
import { NavLink, Outlet } from "react-router";
import { currentTheme, setTheme, type Theme } from "../lib/theme";

function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <svg aria-hidden="true" viewBox="0 0 28 28" className="h-7 w-7">
        <rect width="28" height="28" rx="5" className="fill-paper-raised stroke-rule-strong" />
        <path d="M5 8h18M5 14h18M5 20h18" className="stroke-rule-strong" strokeWidth="1.4" />
        <path d="M13 4v20M15.4 4v20" className="stroke-guard" strokeWidth="1.5" />
      </svg>
      <span className="text-lg font-bold tracking-tight">Ledgerline</span>
      <span className="text-ink-muted">Lab</span>
    </span>
  );
}

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded px-2 py-1 ${isActive ? "text-guard underline decoration-2 underline-offset-[6px]" : "text-ink-muted hover:text-ink"}`;

export function Layout() {
  const [theme, setThemeState] = useState<Theme>(currentTheme);
  const next: Theme = theme === "dark" ? "light" : "dark";

  return (
    <div className="min-h-screen">
      <header className="border-b border-rule">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-2 px-5 py-3">
          <NavLink to="/" aria-label="Ledgerline Lab home">
            <Wordmark />
          </NavLink>
          <nav aria-label="Main" className="flex gap-2">
            <NavLink to="/" end className={linkClass}>
              Attacks
            </NavLink>
            <NavLink to="/coverage" className={linkClass}>
              Coverage
            </NavLink>
          </nav>
          <button
            type="button"
            onClick={() => {
              setTheme(next);
              setThemeState(next);
            }}
            className="ml-auto rounded border border-rule px-2.5 py-1 text-sm text-ink-muted hover:border-rule-strong hover:text-ink"
          >
            {next === "dark" ? "Dark theme" : "Light theme"}
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-5 pt-8 pb-16">
        <Outlet />
      </main>
    </div>
  );
}

import { NavLink, Outlet } from "react-router";
import { ThemeSwitch } from "./ThemeSwitch";

function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <svg aria-hidden="true" viewBox="0 0 28 28" className="h-7 w-7">
        <rect width="28" height="28" rx="8" className="fill-button" />
        <path
          d="M7 9.5h14M7 14h14M7 18.5h14"
          className="stroke-button-ink"
          strokeOpacity="0.35"
          strokeWidth="1.4"
        />
        <path d="M12.6 6v16M15.4 6v16" className="stroke-button-ink" strokeWidth="1.6" />
      </svg>
      <span className="hidden text-[17px] font-semibold tracking-tight sm:inline">Ledgerline</span>
    </span>
  );
}

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-full px-3 py-1.5 text-sm transition-colors ${isActive ? "bg-paper-raised text-ink" : "text-ink-muted hover:text-ink"}`;

export function Layout() {
  return (
    <div className="min-h-screen overflow-x-clip">
      <div className="backdrop" aria-hidden="true" />
      <header className="relative z-20 px-4 pt-4">
        <div className="glass mx-auto flex max-w-6xl flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl px-3 py-2.5 sm:gap-x-6 sm:px-4">
          <NavLink to="/" aria-label="Ledgerline Lab home" className="rounded-lg">
            <Wordmark />
          </NavLink>
          <nav aria-label="Main" className="flex gap-1">
            <NavLink to="/" end className={linkClass}>
              Attacks
            </NavLink>
            <NavLink to="/coverage" className={linkClass}>
              Coverage
            </NavLink>
          </nav>
          <div className="ml-auto">
            <ThemeSwitch />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 pt-12 pb-20 md:px-8">
        <Outlet />
      </main>
    </div>
  );
}

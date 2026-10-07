import { useCoverage } from "../api/queries";
import type { CoverageRow } from "../api/types";
import { CONTROLS } from "../lib/controls";
import { Problem } from "./Problem";

const CELL: Record<CoverageRow["cells"][string], { text: string; className: string }> = {
  required: { text: "Stops it", className: "font-medium text-guard" },
  not_needed: { text: "Not needed", className: "text-ink-muted" },
  not_stopped: { text: "Not stopped yet", className: "text-loss" },
};

export function CoveragePage() {
  const coverage = useCoverage();
  if (coverage.error) return <Problem error={coverage.error} />;

  return (
    <>
      <section className="max-w-4xl pt-6">
        <h1 className="display text-[2.8rem] md:text-[4rem]">Which control stops which attack</h1>
        <p className="mt-4 max-w-[40rem] text-lg text-ink-muted">
          Measured, not claimed: every attack is replayed once with all controls on, then once with each
          control switched off. "Stops it" means the attack succeeds without that control.
        </p>
      </section>

      {coverage.isPending && (
        <p className="mt-8 text-ink-muted" aria-live="polite">
          Replaying every attack with each control switched off. This takes about half a minute the first
          time.
        </p>
      )}

      {coverage.data && (
        <div className="glass mt-10 overflow-x-auto rounded-3xl px-6 py-2">
          <table className="w-full min-w-[52rem] border-collapse text-left">
            <caption className="sr-only">Controls against attacks</caption>
            <thead>
              <tr className="border-b border-rule align-bottom text-sm text-ink-muted">
                <th scope="col" className="py-2 pr-4 font-normal">
                  Attack
                </th>
                <th scope="col" className="py-2 pr-4 font-normal">
                  Without Ledgerline
                </th>
                <th scope="col" className="py-2 pr-4 font-normal">
                  With Ledgerline
                </th>
                {CONTROLS.map((c) => (
                  <th key={c.key} scope="col" className="double-rule py-2 pr-3 pl-3 font-normal">
                    {c.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {coverage.data.rows.map((row) => (
                <tr key={row.scenario_id} className="border-b border-rule align-top last:border-0">
                  <th scope="row" className="py-3 pr-4 font-normal">
                    <span className="block font-medium">{row.title}</span>
                    {row.owasp_mcp.length > 0 && (
                      <span className="block text-sm text-ink-muted">{row.owasp_mcp.join("; ")}</span>
                    )}
                  </th>
                  <td className={`py-3 pr-4 ${row.unprotected === "harmed" ? "text-loss" : "text-safe"}`}>
                    {row.unprotected === "harmed" ? "Secret stolen" : "Safe"}
                  </td>
                  <td
                    className={`py-3 pr-4 font-medium ${row.protected === "harmed" ? "text-loss" : "text-safe"}`}
                  >
                    {row.protected === "harmed" ? "Secret stolen" : "Safe"}
                  </td>
                  {CONTROLS.map((c) => {
                    const status = row.cells[c.key];
                    const cell = status ? CELL[status] : undefined;
                    return (
                      <td key={c.key} className={`double-rule py-3 pr-3 pl-3 ${cell?.className ?? ""}`}>
                        {cell?.text ?? ""}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

import { useEffect, useState } from "react";
import { useVerifyLedger } from "../api/queries";
import type { LedgerRecord, VerifyResult } from "../api/types";
import { controlName } from "../lib/controls";
import { usePrefersReducedMotion } from "../lib/motion";

// The protected side's ledger as a chain you can verify, and tamper with to watch verification fail.

type Row = Record<string, unknown> & Partial<LedgerRecord>;
type Status = "pending" | "ok" | "broken" | "untrusted";

/** What "expected" and "found" mean for each kind of break. */
const LABELS: Record<string, [string, string]> = {
  edited: ["sealed as", "contents hash to"],
  broken_link: ["previous entry", "this entry points to"],
  bad_seq: ["expected number", "found number"],
  wrong_run: ["run", "this entry's run"],
};

const short = (hash: unknown) =>
  typeof hash === "string" && hash.length > 12 ? `${hash.slice(0, 6)}…${hash.slice(-4)}` : String(hash);

function describe(row: Row): { title: string; detail: string; tone: string } {
  const tool = typeof row.tool === "string" ? row.tool : "a tool";
  if (row.kind === "outcome") {
    const status = row.outcome?.status;
    return {
      title: `Result of ${tool}`,
      detail:
        status === "ok" ? "returned normally" : status === "tool_error" ? "returned an error" : "failed",
      tone: "text-ink-muted",
    };
  }
  const decision = row.decision;
  if (decision?.effect === "deny") {
    return {
      title: `Call to ${tool}`,
      detail: `blocked by ${controlName(decision.control ?? "Ledgerline")}`,
      tone: "text-guard",
    };
  }
  return {
    title: `Call to ${tool}`,
    detail: decision?.effect === "allow" ? "allowed" : "?",
    tone: "text-safe",
  };
}

function statusOf(index: number, result: VerifyResult | null, revealed: number): Status {
  if (!result || index >= revealed) return "pending";
  if (result.ok || index < result.verified) return "ok";
  return index === result.problem?.index ? "broken" : "untrusted";
}

const STATUS_TEXT: Record<Status, string> = {
  pending: "",
  ok: "verified",
  broken: "broken here",
  untrusted: "can't be trusted",
};
const STATUS_TONE: Record<Status, string> = {
  pending: "text-ink-muted",
  ok: "text-safe",
  broken: "text-loss",
  untrusted: "text-ink-muted",
};
const LINK_COLOR: Record<Status, string> = {
  pending: "var(--rule-strong)",
  ok: "var(--safe)",
  broken: "var(--loss)",
  untrusted: "var(--rule)",
};

interface Props {
  entries: LedgerRecord[];
  running: boolean;
}

export function LedgerChain({ entries, running }: Props) {
  const verify = useVerifyLedger();
  const reduced = usePrefersReducedMotion();
  const [working, setWorking] = useState<Row[] | null>(null); // a tampered copy, or null for the real ledger
  const [edited, setEdited] = useState<Set<number>>(new Set());
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [draftError, setDraftError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [revealed, setRevealed] = useState(0);
  const [tampering, setTampering] = useState(false);

  const rows: Row[] = working ?? (entries as Row[]);

  // Reveal verification one link at a time: the check really is sequential.
  useEffect(() => {
    if (!result) return;
    const stop = result.ok ? rows.length : (result.problem?.index ?? 0) + 1;
    if (reduced) {
      setRevealed(rows.length);
      return;
    }
    if (revealed >= rows.length) return;
    const timer = window.setTimeout(() => setRevealed((n) => n + 1), revealed < stop ? 90 : 25);
    return () => window.clearTimeout(timer);
  }, [result, revealed, rows.length, reduced]);

  const change = (next: Row[], seq: number) => {
    setWorking(next);
    setEdited((s) => new Set(s).add(seq));
    setResult(null);
    setRevealed(0);
  };

  const flip = (i: number) => {
    const row = rows[i];
    if (!row?.decision) return;
    const effect = row.decision.effect === "deny" ? "allow" : "deny";
    change(
      rows.map((r, j) => (j === i ? { ...r, decision: { ...r.decision, effect } } : r)) as Row[],
      Number(row.seq),
    );
  };

  const remove = (i: number) =>
    change(
      rows.filter((_, j) => j !== i),
      Number(rows[i]?.seq),
    );

  const saveDraft = (i: number) => {
    try {
      const parsed: unknown = JSON.parse(draft);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        setDraftError("An entry is a JSON object.");
        return;
      }
      change(
        rows.map((r, j) => (j === i ? (parsed as Row) : r)),
        Number(rows[i]?.seq),
      );
      setEditing(null);
    } catch (e) {
      setDraftError(e instanceof Error ? e.message : "That isn't valid JSON.");
    }
  };

  const reset = () => {
    setWorking(null);
    setEdited(new Set());
    setEditing(null);
    setResult(null);
    setRevealed(0);
  };

  const runVerify = async () => {
    setResult(null);
    setRevealed(0);
    setResult(await verify.mutateAsync(rows));
  };

  if (entries.length === 0) {
    return (
      <p className="text-ink-muted">
        {running
          ? "Waiting for the first tool call…"
          : "Nothing was recorded in this run. Messages rejected by strict parsing never reach the ledger: they can't be read reliably enough to record."}
      </p>
    );
  }

  const settled = result && revealed >= rows.length;

  return (
    <section aria-labelledby="ledger-heading">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-[44rem]">
          <h2 id="ledger-heading" className="display text-[1.9rem]">
            The ledger
          </h2>
          <p className="mt-2 text-ink-muted">
            Ledgerline wrote every tool call here before forwarding it. Each entry includes the previous
            entry's hash, so changing anything breaks the chain from that point on. Edit an entry the way
            someone with database access could, then verify.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!running && (
            <button
              type="button"
              aria-pressed={tampering}
              onClick={() => setTampering((t) => !t)}
              className="h-11 rounded-full border border-rule-strong px-4 text-sm text-ink-muted transition-transform duration-[160ms] ease-(--ease-out) hover:text-ink active:scale-[0.97] aria-pressed:border-guard aria-pressed:text-guard"
            >
              {tampering ? "Stop tampering" : "Tamper with the ledger"}
            </button>
          )}
          {working && (
            <button
              type="button"
              onClick={reset}
              className="h-11 rounded-full border border-rule-strong px-4 text-sm text-ink-muted transition-transform duration-[160ms] ease-(--ease-out) hover:text-ink active:scale-[0.97]"
            >
              Undo my edits
            </button>
          )}
          <button
            type="button"
            onClick={runVerify}
            disabled={verify.isPending || running}
            className="h-11 rounded-full bg-button px-5 font-medium text-button-ink transition-transform duration-[160ms] ease-(--ease-out) active:scale-[0.97] disabled:opacity-50 disabled:active:scale-100"
          >
            Verify the chain
          </button>
        </div>
      </div>

      <div aria-live="polite" className="mt-5 min-h-[4.5rem]">
        {settled && result.ok && (
          <div className="rounded-2xl border border-safe/25 bg-safe-wash px-5 py-4">
            <p className="font-medium text-safe">Chain intact: all {result.count} entries verified.</p>
            <p className="mt-1 font-mono text-sm break-all text-ink-muted">Head hash {result.head_hash}</p>
          </div>
        )}
        {settled && !result.ok && result.problem && (
          <div className="rounded-2xl border border-loss/25 bg-loss-wash px-5 py-4">
            <p className="font-medium text-loss">{result.problem.message}</p>
            <p className="mt-1 text-sm">
              {result.verified > 0
                ? `Entries 1 to ${result.verified} are intact. Nothing after them can be trusted.`
                : "Nothing in this chain can be trusted."}
            </p>
            {result.problem.expected && result.problem.found && (
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 font-mono text-xs text-ink-muted">
                <dt>{LABELS[result.problem.kind]?.[0] ?? "expected"}</dt>
                <dd className="break-all">{result.problem.expected}</dd>
                <dt>{LABELS[result.problem.kind]?.[1] ?? "found"}</dt>
                <dd className="break-all">{result.problem.found}</dd>
              </dl>
            )}
          </div>
        )}
        {verify.error && <p className="text-loss">Couldn't verify: {verify.error.message}</p>}
      </div>

      <ol className="mt-4" aria-label="Ledger entries, oldest first">
        {rows.map((row, i) => {
          const status = statusOf(i, result, revealed);
          const { title, detail, tone } = describe(row);
          const isEdited = edited.has(Number(row.seq));
          return (
            <li key={`${String(row.seq)}-${String(row.entry_hash)}`} className="relative pl-10">
              {/* the link to the previous entry */}
              <span
                aria-hidden="true"
                className="absolute top-0 bottom-0 left-[0.95rem] w-px transition-colors duration-200"
                style={{ background: i === 0 ? "transparent" : LINK_COLOR[status] }}
              />
              <span
                aria-hidden="true"
                className="absolute top-6 left-[0.55rem] h-3.5 w-3.5 rounded-full border-2 transition-colors duration-200"
                style={{
                  borderColor: LINK_COLOR[status],
                  background: status === "ok" ? "var(--safe)" : "var(--paper)",
                }}
              />
              <article
                aria-label={`Entry ${String(row.seq)}`}
                className={`my-2 rounded-2xl border px-4 py-3.5 transition-colors duration-200 ${status === "broken" ? "border-loss/50 bg-loss-wash" : isEdited ? "border-guard/40 bg-paper-raised" : "border-rule bg-paper-raised"} ${status === "untrusted" ? "opacity-60" : ""}`}
              >
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="display text-[1.5rem] leading-none tabular-nums">{String(row.seq)}</span>
                  <span className="font-medium">{title}</span>
                  <span className={`text-sm ${tone}`}>{detail}</span>
                  {isEdited && <span className="text-sm text-guard">edited by you</span>}
                  <span className={`ml-auto text-sm ${STATUS_TONE[status]}`}>{STATUS_TEXT[status]}</span>
                </div>
                <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 font-mono text-xs text-ink-muted">
                  <dt>previous</dt>
                  <dd className="truncate">{short(row.prev_hash)}</dd>
                  <dt>this entry</dt>
                  <dd className="truncate">{short(row.entry_hash)}</dd>
                </dl>
                {tampering && !running && (
                  <div className="mt-3 flex flex-wrap gap-2 text-sm">
                    {row.kind === "request" && row.decision && (
                      <button
                        type="button"
                        onClick={() => flip(i)}
                        className="rounded-full border border-rule-strong px-3 py-1 hover:bg-paper"
                      >
                        {row.decision.effect === "deny" ? "Rewrite as allowed" : "Rewrite as blocked"}
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(editing === i ? null : i);
                        setDraft(JSON.stringify(row, null, 2));
                        setDraftError(null);
                      }}
                      className="rounded-full border border-rule-strong px-3 py-1 hover:bg-paper"
                    >
                      Edit JSON
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(i)}
                      className="rounded-full border border-rule-strong px-3 py-1 hover:bg-paper"
                    >
                      Delete entry
                    </button>
                  </div>
                )}
                {editing === i && (
                  <div className="mt-3">
                    <label className="sr-only" htmlFor={`edit-${i}`}>
                      Entry {String(row.seq)} as JSON
                    </label>
                    <textarea
                      id={`edit-${i}`}
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      spellCheck={false}
                      rows={14}
                      className="w-full rounded-xl border border-rule-strong bg-paper p-3 font-mono text-xs"
                    />
                    {draftError && <p className="mt-1 text-sm text-loss">{draftError}</p>}
                    <div className="mt-2 flex gap-2 text-sm">
                      <button
                        type="button"
                        onClick={() => saveDraft(i)}
                        className="rounded-full bg-button px-4 py-1.5 font-medium text-button-ink"
                      >
                        Save edit
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditing(null)}
                        className="rounded-full border border-rule-strong px-4 py-1.5"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </article>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

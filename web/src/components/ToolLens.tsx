import { diffLines } from "diff";
import type { ToolDef } from "../api/types";

interface Props {
  pinned: ToolDef[] | undefined;
  current: ToolDef[]; // what the server sends now (latest unprotected listing)
  shownWithLedgerline: ToolDef[]; // what the model sees through Ledgerline
}

const HIDDEN = /(<IMPORTANT>[\s\S]*?<\/IMPORTANT>)/g;

/** The full description, with hidden instructions highlighted. */
function ModelView({ text }: { text: string }) {
  return (
    <p className="font-mono text-[13px] leading-snug whitespace-pre-wrap break-words">
      {text.split(HIDDEN).map((part, i) =>
        part.startsWith("<IMPORTANT>") ? (
          // biome-ignore lint/suspicious/noArrayIndexKey: parts of one fixed string, never reordered
          <mark key={i} className="bg-loss-wash text-loss">
            {part}
          </mark>
        ) : (
          // biome-ignore lint/suspicious/noArrayIndexKey: as above
          <span key={i}>{part}</span>
        ),
      )}
    </p>
  );
}

function Diff({ before, after }: { before: string; after: string }) {
  return (
    <pre className="font-mono text-[13px] leading-snug whitespace-pre-wrap break-words">
      {diffLines(before, after).map((part, i) => (
        <span
          // biome-ignore lint/suspicious/noArrayIndexKey: diff parts are positional
          key={i}
          className={
            part.added ? "bg-loss-wash text-loss" : part.removed ? "text-ink-muted line-through" : ""
          }
        >
          {part.added ? "+ " : part.removed ? "- " : ""}
          {part.value}
        </span>
      ))}
    </pre>
  );
}

export function ToolLens({ pinned, current, shownWithLedgerline }: Props) {
  const names = [...new Set([...(pinned ?? []).map((t) => t.name), ...current.map((t) => t.name)])];
  if (names.length === 0)
    return <p className="text-ink-muted">Tools appear here once the agent has listed them.</p>;

  return (
    <div className="space-y-8">
      <p className="max-w-prose text-ink-muted">
        Most AI hosts show you only the first line of a tool's description. The model reads all of it,
        including anything hidden further down.
      </p>
      {names.map((name) => {
        const approved = pinned?.find((t) => t.name === name);
        const now = current.find((t) => t.name === name) ?? approved;
        if (!now) return null;
        const changed = approved && approved.sha256 !== now.sha256;
        const visible = shownWithLedgerline.some((t) => t.name === name);
        return (
          <section key={name} className="border-t border-rule pt-4" aria-labelledby={`tool-${name}`}>
            <h3 id={`tool-${name}`} className="font-mono text-lg font-bold">
              {name}
            </h3>
            <p className="mt-1 text-sm">
              {!approved && <span className="text-loss">Never reviewed or approved. </span>}
              {changed && <span className="text-loss">Changed since you approved it. </span>}
              {approved && !changed && <span className="text-safe">Same as the version you approved. </span>}
              <span className={visible ? "text-ink-muted" : "text-guard"}>
                {visible ? "Ledgerline shows it to the model." : "Ledgerline hides it from the model."}
              </span>
            </p>
            <div className="mt-3 grid gap-6 md:grid-cols-2">
              <div>
                <h4 className="mb-1 font-bold">What you see</h4>
                <p className="rounded-sm border border-rule bg-paper-raised px-3 py-2">
                  {now.description.split("\n")[0]}
                </p>
              </div>
              <div>
                <h4 className="mb-1 font-bold">What the model reads</h4>
                <div className="rounded-sm border border-rule bg-paper-raised px-3 py-2">
                  <ModelView text={now.description} />
                </div>
              </div>
            </div>
            {changed && approved && (
              <div className="mt-4">
                <h4 className="mb-1 font-bold">Approved version compared with what the server sends now</h4>
                <div className="rounded-sm border border-rule bg-paper-raised px-3 py-2">
                  <Diff before={approved.description} after={now.description} />
                </div>
                <p className="mt-1 font-mono text-xs text-ink-muted">
                  fingerprint {approved.sha256.slice(0, 12)} → {now.sha256.slice(0, 12)}
                </p>
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

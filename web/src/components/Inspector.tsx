import * as Dialog from "@radix-ui/react-dialog";
import { CONTROLS } from "../lib/controls";
import type { Entry } from "../lib/runState";
import { JsonView } from "./JsonView";
import { entryLabel } from "./LedgerEntries";

interface Props {
  entry: Entry | null;
  onClose: () => void;
}

function Explanation({ entry }: { entry: Entry }) {
  switch (entry.type) {
    case "decision": {
      const control = CONTROLS.find((c) => c.id === entry.control);
      return control ? <p>{control.explain}</p> : null;
    }
    case "message":
      return entry.internal ? (
        <p>
          Ledgerline asked the server for the tool's current definition before forwarding the call. The AI
          host never sees this exchange.
        </p>
      ) : (
        <p>The exact JSON-RPC message that crossed this hop.</p>
      );
    case "exfiltration":
      return (
        <p>
          What the malicious server received. In the Lab this is always a fake value from a temporary file.
        </p>
      );
    default:
      return null;
  }
}

export function Inspector({ entry, onClose }: Props) {
  return (
    <Dialog.Root open={entry !== null} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed inset-y-0 right-0 flex w-full max-w-xl flex-col gap-4 overflow-y-auto border-l border-rule bg-paper p-6 shadow-2xl">
          {entry && (
            <>
              <div>
                <Dialog.Title className="text-xl font-medium">{entryLabel(entry).who}</Dialog.Title>
                <Dialog.Description className="mt-1 break-words text-ink-muted">
                  {entryLabel(entry).what}
                </Dialog.Description>
              </div>
              <div className="max-w-prose space-y-2">
                <Explanation entry={entry} />
              </div>
              <JsonView value={entry.type === "message" ? entry.body : entry} />
              <Dialog.Close className="self-start rounded-full border border-rule-strong px-4 py-1.5 hover:bg-paper-raised">
                Close
              </Dialog.Close>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

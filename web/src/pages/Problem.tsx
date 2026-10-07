import { ApiError } from "../api/client";

/** Explains what went wrong and what to do next. */
export function Problem({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.status === 401) {
    return (
      <section className="max-w-prose">
        <h1 className="display text-[2.4rem]">Open the Lab from its link</h1>
        <p className="mt-2">
          The Lab only answers browsers that arrived through the link{" "}
          <code className="font-mono">ledgerline ui</code> printed in your terminal. Open that link again, or
          restart <code className="font-mono">ledgerline ui</code> to get a new one.
        </p>
      </section>
    );
  }
  return (
    <section className="max-w-prose">
      <h1 className="display text-[2.4rem]">The Lab couldn't load this</h1>
      <p className="mt-2">
        {error instanceof Error ? error.message : String(error)}. Check that{" "}
        <code className="font-mono">ledgerline ui</code> is still running in your terminal.
      </p>
    </section>
  );
}

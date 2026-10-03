interface Props {
  owaspMcp: string[];
  owaspAsi: string[];
}

/** OWASP categories, written out (they are lookup keys, not decoration). */
export function Tags({ owaspMcp, owaspAsi }: Props) {
  if (owaspMcp.length + owaspAsi.length === 0) return null;
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
      {owaspMcp.length > 0 && (
        <>
          <dt className="text-ink-muted">OWASP MCP Top 10</dt>
          <dd>{owaspMcp.join("; ")}</dd>
        </>
      )}
      {owaspAsi.length > 0 && (
        <>
          <dt className="text-ink-muted">OWASP Agentic Top 10</dt>
          <dd>{owaspAsi.join("; ")}</dd>
        </>
      )}
    </dl>
  );
}

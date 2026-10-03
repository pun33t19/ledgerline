// Pretty-printed JSON with light colouring. Rendered as text nodes only (never as HTML).
interface Props {
  value: unknown;
}

const TOKEN = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;

export function JsonView({ value }: Props) {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(TOKEN)) {
    const index = match.index ?? 0;
    if (index > last) parts.push(text.slice(last, index));
    const [whole, str, colon, literal] = match;
    const className = str && colon ? "text-guard" : str ? "text-safe" : literal ? "text-loss" : "text-ink";
    parts.push(
      <span key={index} className={className}>
        {whole}
      </span>,
    );
    last = index + whole.length;
  }
  parts.push(text.slice(last));
  return (
    <pre className="overflow-x-auto rounded-sm border border-rule bg-paper p-3 font-mono text-[13px] leading-snug whitespace-pre-wrap break-words">
      {parts}
    </pre>
  );
}

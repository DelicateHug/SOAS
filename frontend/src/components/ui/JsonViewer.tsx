import { useState } from "react";
import { cn } from "@/lib/utils";

interface Props {
  data: Record<string, unknown>;
  maxHeight?: string;
  className?: string;
}

function JsonNode({ value, depth = 0 }: { value: unknown; depth?: number }) {
  const [collapsed, setCollapsed] = useState(depth > 2);

  if (value === null) return <span className="text-[var(--color-text-muted)]">null</span>;
  if (typeof value === "boolean") return <span className="text-purple-400">{String(value)}</span>;
  if (typeof value === "number") return <span className="text-cyan-400">{value}</span>;
  if (typeof value === "string") return <span className="text-green-400">"{value}"</span>;

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-[var(--color-text-muted)]">[]</span>;
    if (collapsed) {
      return (
        <button onClick={() => setCollapsed(false)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          [{value.length} items]
        </button>
      );
    }
    return (
      <span>
        <button onClick={() => setCollapsed(true)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">[</button>
        <div className="pl-4">
          {value.map((item, i) => (
            <div key={i}>
              <JsonNode value={item} depth={depth + 1} />
              {i < value.length - 1 && ","}
            </div>
          ))}
        </div>
        ]
      </span>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span className="text-[var(--color-text-muted)]">{"{}"}</span>;
    if (collapsed) {
      return (
        <button onClick={() => setCollapsed(false)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          {"{"}...{entries.length} keys{"}"}
        </button>
      );
    }
    return (
      <span>
        <button onClick={() => setCollapsed(true)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">{"{"}</button>
        <div className="pl-4">
          {entries.map(([key, val], i) => (
            <div key={key}>
              <span className="text-blue-400">"{key}"</span>
              <span className="text-[var(--color-text-muted)]">: </span>
              <JsonNode value={val} depth={depth + 1} />
              {i < entries.length - 1 && ","}
            </div>
          ))}
        </div>
        {"}"}
      </span>
    );
  }

  return <span>{String(value)}</span>;
}

export function JsonViewer({ data, maxHeight = "max-h-96", className }: Props) {
  const [raw, setRaw] = useState(false);

  return (
    <div className={cn("rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]", className)}>
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--color-border)]">
        <span className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] font-medium">JSON</span>
        <button
          onClick={() => setRaw(!raw)}
          className="text-[10px] px-1.5 py-0.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-2)]"
        >
          {raw ? "Tree" : "Raw"}
        </button>
      </div>
      <div className={cn("overflow-auto p-3 text-xs font-mono leading-relaxed", maxHeight)}>
        {raw ? (
          <pre className="whitespace-pre-wrap">{JSON.stringify(data, null, 2)}</pre>
        ) : (
          <JsonNode value={data} />
        )}
      </div>
    </div>
  );
}

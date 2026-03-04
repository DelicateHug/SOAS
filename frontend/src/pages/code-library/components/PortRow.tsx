/**
 * Single port definition row with name, type, required toggle, and remove button.
 */

import { Trash2, Lock } from "lucide-react";
import type { PortDefinition } from "./PortBuilder";

const PORT_TYPES = ["STRING", "INTEGER", "FLOAT", "BOOLEAN", "LIST", "DICT", "OBJECT", "ANY"] as const;

interface PortRowProps {
  port: PortDefinition;
  onUpdate: (updated: PortDefinition) => void;
  onRemove: () => void;
  isLocked?: boolean;
  direction: "input" | "output";
}

export function PortRow({ port, onUpdate, onRemove, isLocked, direction }: PortRowProps) {
  if (isLocked) {
    return (
      <div className="flex items-center gap-2 px-2 py-1.5 rounded bg-[hsl(var(--muted))] opacity-60">
        <Lock className="w-3 h-3 shrink-0" />
        <span className="text-xs font-mono flex-1">{port.name}</span>
        <span className="text-[10px] text-[hsl(var(--muted-foreground))]">{port.type}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <input
        type="text"
        value={port.name}
        onChange={(e) => onUpdate({ ...port, name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "") })}
        placeholder="port_name"
        className="flex-1 min-w-0 px-2 py-1 text-xs font-mono border border-[hsl(var(--input))] rounded bg-transparent"
      />
      <select
        value={port.type}
        onChange={(e) => onUpdate({ ...port, type: e.target.value })}
        className="w-20 px-1 py-1 text-xs border border-[hsl(var(--input))] rounded bg-[hsl(var(--background))]"
      >
        {PORT_TYPES.map((t) => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>
      {direction === "input" && (
        <label className="flex items-center gap-1 text-[10px] shrink-0" title="Required">
          <input
            type="checkbox"
            checked={port.required}
            onChange={(e) => onUpdate({ ...port, required: e.target.checked })}
            className="rounded border-[hsl(var(--input))] w-3 h-3"
          />
          Req
        </label>
      )}
      <button
        type="button"
        onClick={onRemove}
        className="p-1 text-[hsl(var(--muted-foreground))] hover:text-red-400 transition-colors"
        title="Remove port"
      >
        <Trash2 className="w-3 h-3" />
      </button>
    </div>
  );
}

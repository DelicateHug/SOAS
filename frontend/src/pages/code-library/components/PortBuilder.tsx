/**
 * Port builder section for defining input or output ports on a code block.
 * Shows locked FLOW ports at top, then user-configurable data ports with add/remove.
 */

import { Plus } from "lucide-react";
import { PortRow } from "./PortRow";

export interface PortDefinition {
  name: string;
  type: string;
  description: string;
  required: boolean;
}

const MAX_CUSTOM_PORTS = 10;

interface PortBuilderProps {
  label: string;
  ports: PortDefinition[];
  onChange: (ports: PortDefinition[]) => void;
  direction: "input" | "output";
}

/** The locked FLOW port that's always present */
function getFlowPort(direction: "input" | "output"): PortDefinition {
  return direction === "input"
    ? { name: "exec_in", type: "FLOW", description: "Execution input", required: false }
    : { name: "exec_out", type: "FLOW", description: "Execution output", required: false };
}

export function PortBuilder({ label, ports, onChange, direction }: PortBuilderProps) {
  const flowPort = getFlowPort(direction);

  const addPort = () => {
    if (ports.length >= MAX_CUSTOM_PORTS) return;
    const baseName = direction === "input" ? "input" : "output";
    let idx = ports.length + 1;
    let name = `${baseName}_${idx}`;
    const existingNames = new Set(ports.map((p) => p.name));
    while (existingNames.has(name)) {
      idx++;
      name = `${baseName}_${idx}`;
    }
    onChange([...ports, { name, type: "ANY", description: "", required: false }]);
  };

  const updatePort = (index: number, updated: PortDefinition) => {
    const next = [...ports];
    next[index] = updated;
    onChange(next);
  };

  const removePort = (index: number) => {
    onChange(ports.filter((_, i) => i !== index));
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
          {label}
        </label>
        <button
          type="button"
          onClick={addPort}
          disabled={ports.length >= MAX_CUSTOM_PORTS}
          className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] disabled:opacity-40 transition-colors"
        >
          <Plus className="w-3 h-3" />
          Add
        </button>
      </div>

      <div className="space-y-1.5">
        {/* Locked FLOW port */}
        <PortRow
          port={flowPort}
          onUpdate={() => {}}
          onRemove={() => {}}
          isLocked
          direction={direction}
        />

        {/* User-configurable data ports */}
        {ports.map((port, index) => (
          <PortRow
            key={index}
            port={port}
            onUpdate={(updated) => updatePort(index, updated)}
            onRemove={() => removePort(index)}
            direction={direction}
          />
        ))}

        {ports.length === 0 && (
          <div className="text-[10px] text-[var(--color-text-muted)] italic px-2 py-1">
            No data ports. Click + to add one.
          </div>
        )}
      </div>
    </div>
  );
}

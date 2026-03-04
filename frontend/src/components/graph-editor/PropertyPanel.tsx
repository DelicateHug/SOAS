/**
 * Right panel showing the selected node's properties and inline port values.
 * Dynamically renders form fields based on the node type's property definitions.
 */

import { useState, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { useUpdateNodeInternals } from "@xyflow/react";
import { useQuery } from "@tanstack/react-query";
import { useGraphEditorStore } from "./stores/graphEditorStore";
import type { CustomNodeData } from "./utils/graphConversion";
import type { NodePropertyDef, VP2Port } from "./types/graph";
import { PORT_TYPE_COLORS } from "./utils/portColors";
import type { PortType } from "./types/graph";
import { Settings2, X, HelpCircle } from "lucide-react";
import { AutomationSelectField } from "./AutomationSelectField";
import type { AutomationInputDef } from "./AutomationSelectField";
import { IncidentVariableSelectField } from "./IncidentVariableSelectField";
import { SOASVariableSelectField } from "./SOASVariableSelectField";
import { api } from "@/lib/api";

interface PropertyPanelProps {
  isReadOnly?: boolean;
}

export function PropertyPanel({ isReadOnly }: PropertyPanelProps) {
  const selectedNode = useGraphEditorStore(
    (s) => (s.selectedNodeId ? s.nodes.find((n) => n.id === s.selectedNodeId) : null)
  );
  const graphId = useGraphEditorStore((s) => s.graphId);
  const updateNodeProperty = useGraphEditorStore((s) => s.updateNodeProperty);
  const updateNodeInlineValue = useGraphEditorStore((s) => s.updateNodeInlineValue);
  const updateNodeDynamicPortsRaw = useGraphEditorStore((s) => s.updateNodeDynamicPorts);
  const updateNodeInternals = useUpdateNodeInternals();
  const selectNode = useGraphEditorStore((s) => s.selectNode);

  // Wrap dynamic port update to also refresh React Flow handle positions
  const updateNodeDynamicPorts: typeof updateNodeDynamicPortsRaw = (nodeId, inputDefs) => {
    updateNodeDynamicPortsRaw(nodeId, inputDefs);
    // Allow React to render the new handles before recalculating positions
    requestAnimationFrame(() => updateNodeInternals(nodeId));
  };

  if (!selectedNode) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-[hsl(var(--muted-foreground))]">
            <Settings2 className="w-8 h-8 mx-auto mb-2 opacity-40" />
            <p className="text-xs">Select a node to edit its properties</p>
          </div>
        </div>
      </div>
    );
  }

  const data = selectedNode.data as CustomNodeData;
  const properties = data.catalogEntry?.properties || [];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-2 border-b border-[hsl(var(--border))] flex items-center justify-between gap-1">
        <div className="min-w-0 flex-1">
          <h2 className="text-xs font-semibold truncate">{data.label}</h2>
          <p className="text-[10px] text-[hsl(var(--muted-foreground))] truncate">
            {data.type}
          </p>
        </div>
        <button
          onClick={() => selectNode(null)}
          className="p-0.5 hover:bg-[hsl(var(--accent))] rounded flex-shrink-0"
          title="Deselect"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Scrollable content */}
      <div className={`flex-1 overflow-y-auto ${isReadOnly ? "opacity-60 pointer-events-none" : ""}`}>
        {/* Node properties */}
        {properties.length > 0 && (
          <div className="p-3 border-b border-[hsl(var(--border))]">
            <h3 className="text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider mb-2">
              Properties
            </h3>
            <div className="space-y-3">
              {properties.map((prop) => (
                <PropertyField
                  key={prop.name}
                  prop={prop}
                  value={data.properties[prop.name]}
                  onChange={(value) =>
                    updateNodeProperty(selectedNode.id, prop.name, value)
                  }
                  nodeId={selectedNode.id}
                  currentAutomationId={graphId}
                  updateNodeProperty={updateNodeProperty}
                  updateNodeDynamicPorts={updateNodeDynamicPorts}
                />
              ))}
            </div>
          </div>
        )}

        {/* Input port inline values */}
        {data.inputs.length > 0 && (
          <div className="p-3">
            <h3 className="text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider mb-2">
              Input Defaults
            </h3>
            <div className="space-y-3">
              {data.inputs
                .filter((port) => port.type !== "FLOW")
                .map((port) => (
                  <InlineValueEditor
                    key={port.name}
                    port={port}
                    onChange={(value) =>
                      updateNodeInlineValue(selectedNode.id, port.name, value)
                    }
                  />
                ))}
            </div>
          </div>
        )}

        {/* Output ports (read-only info) */}
        {data.outputs.length > 0 && (
          <div className="p-3 border-t border-[hsl(var(--border))]">
            <h3 className="text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider mb-2">
              Outputs
            </h3>
            <div className="space-y-1">
              {data.outputs.map((port) => (
                <div key={port.name} className="flex items-center gap-2">
                  <div
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{
                      backgroundColor:
                        PORT_TYPE_COLORS[port.type as PortType] ||
                        PORT_TYPE_COLORS.ANY,
                    }}
                  />
                  <span className="text-xs truncate">
                    {port.label || port.name}
                  </span>
                  <span className="text-[10px] text-[hsl(var(--muted-foreground))] ml-auto">
                    {port.type}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** Tooltip component for property descriptions — renders via portal to escape overflow:hidden */
function PropertyTooltip({ text }: { text: string }) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const iconRef = useRef<HTMLSpanElement>(null);

  const handleEnter = useCallback(() => {
    if (iconRef.current) {
      const rect = iconRef.current.getBoundingClientRect();
      setPos({ x: rect.left + rect.width / 2, y: rect.top });
    }
  }, []);

  return (
    <span ref={iconRef} className="inline-flex" onMouseEnter={handleEnter} onMouseLeave={() => setPos(null)}>
      <HelpCircle className="w-3 h-3 text-[hsl(var(--muted-foreground))] cursor-help" />
      {pos &&
        createPortal(
          <span
            className="fixed z-[9999] px-2 py-1 text-[11px] text-white bg-gray-900 rounded shadow-lg whitespace-normal max-w-[240px] w-max leading-normal pointer-events-none"
            style={{ left: pos.x, top: pos.y, transform: "translate(-50%, -100%) translateY(-6px)" }}
          >
            {text}
            <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
          </span>,
          document.body
        )}
    </span>
  );
}

/** Select field for choosing from the current automation's defined inputs */
function AutomationInputSelectField({
  value,
  automationId,
  onChange,
}: {
  value: string;
  automationId?: string;
  onChange: (value: string) => void;
}) {
  const { data: automation } = useQuery({
    queryKey: ["automation", automationId],
    queryFn: () =>
      api.get<{ parameters: AutomationInputDef[] }>(
        `/automations/${automationId}`
      ),
    enabled: !!automationId,
  });

  const parameters = automation?.parameters || [];

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))]"
    >
      <option value="">{parameters.length === 0 ? "No inputs defined" : "-- Select input --"}</option>
      {parameters.map((param) => (
        <option key={param.name} value={param.name}>
          {param.name} ({param.type})
        </option>
      ))}
    </select>
  );
}

/** Render a property form field based on its type */
function PropertyField({
  prop,
  value,
  onChange,
  nodeId,
  currentAutomationId,
  updateNodeProperty,
  updateNodeDynamicPorts,
}: {
  prop: NodePropertyDef;
  value: unknown;
  onChange: (value: unknown) => void;
  nodeId: string;
  currentAutomationId?: string;
  updateNodeProperty: (nodeId: string, property: string, value: unknown) => void;
  updateNodeDynamicPorts: (
    nodeId: string,
    inputDefs: Array<{ name: string; type: string; required: boolean; default_value: unknown; description: string }>
  ) => void;
}) {
  const inputClasses =
    "w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))]";

  return (
    <div>
      <div className="flex items-center gap-1 mb-1">
        <label className="text-xs font-medium">
          {prop.label}
        </label>
        {prop.description && <PropertyTooltip text={prop.description} />}
      </div>

      {prop.type === "boolean" ? (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
            className="rounded border-[hsl(var(--input))]"
          />
          <span className="text-xs">{value ? "Enabled" : "Disabled"}</span>
        </label>
      ) : prop.type === "number" ? (
        <input
          type="number"
          value={value != null ? String(value) : ""}
          onChange={(e) =>
            onChange(e.target.value ? Number(e.target.value) : null)
          }
          placeholder={prop.placeholder}
          className={inputClasses}
        />
      ) : prop.type === "select" && prop.options ? (
        <select
          value={String(value || "")}
          onChange={(e) => onChange(e.target.value)}
          className={inputClasses}
        >
          <option value="">{prop.placeholder || "-- Select --"}</option>
          {prop.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      ) : prop.type === "code" ? (
        <textarea
          value={String(value || "")}
          onChange={(e) => onChange(e.target.value)}
          className={`${inputClasses} font-mono`}
          rows={6}
          spellCheck={false}
          placeholder={prop.placeholder}
        />
      ) : prop.type === "json" ? (
        <textarea
          value={
            typeof value === "string"
              ? value
              : value != null
                ? JSON.stringify(value, null, 2)
                : ""
          }
          onChange={(e) => {
            try {
              onChange(JSON.parse(e.target.value));
            } catch {
              onChange(e.target.value);
            }
          }}
          className={`${inputClasses} font-mono`}
          rows={4}
          spellCheck={false}
          placeholder={prop.placeholder || "{}"}
        />
      ) : prop.type === "automation_select" ? (
        <AutomationSelectField
          value={String(value || "")}
          currentAutomationId={currentAutomationId}
          onChange={(id, name, parameters) => {
            onChange(id);
            updateNodeProperty(nodeId, "automation_name", name);
            // Store parameter definitions for serialization and dynamic port restoration
            updateNodeProperty(nodeId, "_input_defs", parameters);
            // Update the node's input ports to match the selected automation's inputs
            updateNodeDynamicPorts(nodeId, parameters);
          }}
        />
      ) : prop.type === "automation_input_select" ? (
        <AutomationInputSelectField
          value={String(value || "")}
          automationId={currentAutomationId}
          onChange={(v) => onChange(v)}
        />
      ) : prop.type === "soas_variable_select" ? (
        <SOASVariableSelectField
          value={String(value || "")}
          onChange={(name) => onChange(name)}
        />
      ) : prop.type === "incident_variable_select" ? (
        <IncidentVariableSelectField
          value={String(value || "")}
          onChange={(name) => onChange(name)}
        />
      ) : (
        <input
          type="text"
          value={String(value || "")}
          onChange={(e) => onChange(e.target.value)}
          placeholder={prop.placeholder}
          className={inputClasses}
        />
      )}
    </div>
  );
}

/** Editor for an input port's inline default value */
function InlineValueEditor({
  port,
  onChange,
}: {
  port: VP2Port;
  onChange: (value: unknown) => void;
}) {
  const portColor =
    PORT_TYPE_COLORS[port.type as PortType] || PORT_TYPE_COLORS.ANY;

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1">
        <div
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ backgroundColor: portColor }}
        />
        <label className="text-xs font-medium truncate">
          {port.label || port.name}
        </label>
        {port.required && (
          <span className="text-red-400 text-xs" title="Required">*</span>
        )}
        <span className="text-[10px] text-[hsl(var(--muted-foreground))] ml-auto">
          {port.type}
        </span>
      </div>

      {port.type === "BOOLEAN" ? (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={!!port.inline_value}
            onChange={(e) => onChange(e.target.checked)}
            className="rounded border-[hsl(var(--input))]"
          />
          <span className="text-xs">
            {port.inline_value ? "true" : "false"}
          </span>
        </label>
      ) : port.type === "INTEGER" || port.type === "FLOAT" ? (
        <input
          type="number"
          value={port.inline_value != null ? String(port.inline_value) : ""}
          onChange={(e) =>
            onChange(e.target.value ? Number(e.target.value) : null)
          }
          step={port.type === "FLOAT" ? "0.01" : "1"}
          className="w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))]"
        />
      ) : (
        <input
          type="text"
          value={port.inline_value != null ? String(port.inline_value) : ""}
          onChange={(e) => onChange(e.target.value || null)}
          placeholder={`Default ${port.type.toLowerCase()}`}
          className="w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))]"
        />
      )}
    </div>
  );
}

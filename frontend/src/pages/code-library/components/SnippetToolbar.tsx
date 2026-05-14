/**
 * Toolbar with grouped snippet buttons for inserting code at cursor position.
 * Covers incident variables, SOAS variables, inputs/outputs, and utilities.
 */

import { useState, useRef, useEffect } from "react";
import { ShieldAlert, Database, ArrowRightLeft, Wrench, ChevronDown } from "lucide-react";
import type { CodeEditorPaneHandle } from "./CodeEditorPane";

interface Snippet {
  label: string;
  code: string;
  description: string;
}

interface SnippetGroup {
  title: string;
  icon: React.ReactNode;
  snippets: Snippet[];
}

const SNIPPET_GROUPS: SnippetGroup[] = [
  {
    title: "Incident",
    icon: <ShieldAlert className="w-3.5 h-3.5" />,
    snippets: [
      { label: "Get Var", code: 'get_incident_var("name", default=None)', description: "Get an incident variable" },
      { label: "Set Var", code: 'set_incident_var("name", value)', description: "Set an incident variable" },
      { label: "Get All Data", code: "incident_data = get_incident_data()", description: "Get all incident metadata" },
    ],
  },
  {
    title: "SOAS Vars",
    icon: <Database className="w-3.5 h-3.5" />,
    snippets: [
      { label: "Get Var", code: 'get_soas_var("name", default=None)', description: "Get a SOAS application variable" },
      { label: "Set Var", code: 'set_soas_var("name", value)', description: "Set a SOAS application variable" },
    ],
  },
  {
    title: "I/O",
    icon: <ArrowRightLeft className="w-3.5 h-3.5" />,
    snippets: [
      { label: "Read Input", code: 'value = inputs["value"]', description: "Read a value from input ports" },
      { label: "Set Output", code: 'outputs["result"] = value', description: "Write a value to output ports" },
      { label: "All Inputs", code: "for key, val in inputs.items():\n    pass", description: "Iterate all input values" },
    ],
  },
  {
    title: "Utils",
    icon: <Wrench className="w-3.5 h-3.5" />,
    snippets: [
      { label: "Global Store", code: 'globals["key"] = value', description: "Store a value in persistent globals" },
      { label: "Print Debug", code: 'print(f"DEBUG: {value}")', description: "Print debug output" },
    ],
  },
];

interface SnippetToolbarProps {
  editorRef: React.RefObject<CodeEditorPaneHandle | null>;
}

function SnippetDropdown({ group, editorRef }: { group: SnippetGroup; editorRef: React.RefObject<CodeEditorPaneHandle | null> }) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={dropdownRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] transition-colors"
      >
        {group.icon}
        {group.title}
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 min-w-[220px] py-1 rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] shadow-lg">
          {group.snippets.map((snippet) => (
            <button
              key={snippet.label}
              type="button"
              className="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-surface-2)] transition-colors"
              onClick={() => {
                editorRef.current?.insertAtCursor(snippet.code);
                setOpen(false);
              }}
            >
              <div className="font-medium">{snippet.label}</div>
              <div className="text-[var(--color-text-muted)] text-[10px] font-mono mt-0.5 truncate">
                {snippet.code}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function SnippetToolbar({ editorRef }: SnippetToolbarProps) {
  return (
    <div className="flex items-center gap-2 px-1 py-1.5 border-b border-[var(--color-border)] bg-[var(--color-bg)]">
      <span className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] font-medium mr-1">
        Insert
      </span>
      {SNIPPET_GROUPS.map((group) => (
        <SnippetDropdown key={group.title} group={group} editorRef={editorRef} />
      ))}
    </div>
  );
}

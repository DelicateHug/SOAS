/**
 * IDE-like modal dialog for creating or editing a code library block.
 * Two-column layout: left sidebar for metadata/ports, right side for code editor.
 */

import { useState, useRef } from "react";
import { X } from "lucide-react";
import {
  useCreateBlock,
  useUpdateBlock,
  type CodeLibraryBlock,
} from "@/components/graph-editor/hooks/useCodeLibrary";
import { CodeEditorPane, type CodeEditorPaneHandle } from "./components/CodeEditorPane";
import { SnippetToolbar } from "./components/SnippetToolbar";
import { PortBuilder, type PortDefinition } from "./components/PortBuilder";
import { NodePreview } from "./components/NodePreview";
import { EXAMPLE_TEMPLATES } from "./components/ExampleCodeTemplates";

interface CodeBlockEditorProps {
  block?: CodeLibraryBlock;
  onClose: () => void;
}

/** Extract user-defined data ports (non-FLOW) from stored port array */
function extractDataPorts(ports: Array<{ name: string; type: string; description?: string; required?: boolean }> | null | undefined): PortDefinition[] {
  if (!ports) return [];
  return ports
    .filter((p) => p.type !== "FLOW")
    .map((p) => ({
      name: p.name,
      type: p.type,
      description: p.description || "",
      required: p.required || false,
    }));
}

/** Build the full port array including the locked FLOW port */
function buildPortArray(dataPorts: PortDefinition[], direction: "input" | "output"): Array<{ name: string; type: string; description: string; required: boolean }> {
  const flowPort = direction === "input"
    ? { name: "exec_in", type: "FLOW", description: "Execution input", required: false }
    : { name: "exec_out", type: "FLOW", description: "Execution output", required: false };
  return [flowPort, ...dataPorts];
}

const DEFAULT_INPUT_PORTS: PortDefinition[] = [
  { name: "value", type: "ANY", description: "Input value", required: false },
];

const DEFAULT_OUTPUT_PORTS: PortDefinition[] = [
  { name: "result", type: "ANY", description: "Result value", required: false },
];

export function CodeBlockEditor({ block, onClose }: CodeBlockEditorProps) {
  const isEditing = !!block;
  const [name, setName] = useState(block?.name || "");
  const [description, setDescription] = useState(block?.description || "");
  const initialLang = (block?.language as "python" | "javascript" | "bash") || "python";
  const [language, setLanguage] = useState<"python" | "javascript" | "bash">(initialLang);
  const [code, setCode] = useState(
    block?.code || EXAMPLE_TEMPLATES[initialLang] || ""
  );
  const [isPublic, setIsPublic] = useState(block?.is_public || false);
  const [tags, setTags] = useState(block?.tags?.join(", ") || "");

  // Port state: extract data ports from block, or use defaults for new blocks
  const [inputPorts, setInputPorts] = useState<PortDefinition[]>(
    isEditing ? extractDataPorts(block?.input_ports) : DEFAULT_INPUT_PORTS
  );
  const [outputPorts, setOutputPorts] = useState<PortDefinition[]>(
    isEditing ? extractDataPorts(block?.output_ports) : DEFAULT_OUTPUT_PORTS
  );

  // Track which template was last applied so we can swap on language change
  const lastTemplateRef = useRef<string>(isEditing ? "" : EXAMPLE_TEMPLATES[initialLang] || "");

  const editorRef = useRef<CodeEditorPaneHandle>(null);

  const createBlock = useCreateBlock();
  const updateBlock = useUpdateBlock();
  const isSaving = createBlock.isPending || updateBlock.isPending;

  const handleLanguageChange = (newLang: "python" | "javascript" | "bash") => {
    // If code still matches the template, swap to new language's template
    if (code === lastTemplateRef.current && !isEditing) {
      const newTemplate = EXAMPLE_TEMPLATES[newLang] || "";
      setCode(newTemplate);
      lastTemplateRef.current = newTemplate;
    }
    setLanguage(newLang);
  };

  const handleSave = () => {
    const tagList = tags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    const fullInputPorts = buildPortArray(inputPorts, "input");
    const fullOutputPorts = buildPortArray(outputPorts, "output");

    if (isEditing) {
      updateBlock.mutate(
        {
          blockId: block.id,
          name,
          description: description || undefined,
          code,
          language,
          is_public: isPublic,
          tags: tagList,
          input_ports: fullInputPorts,
          output_ports: fullOutputPorts,
        },
        { onSuccess: onClose }
      );
    } else {
      createBlock.mutate(
        {
          name,
          description: description || undefined,
          code,
          language,
          is_public: isPublic,
          tags: tagList,
          input_ports: fullInputPorts,
          output_ports: fullOutputPorts,
        },
        { onSuccess: onClose }
      );
    }
  };

  const inputClasses = "w-full px-2.5 py-1.5 text-sm border border-[hsl(var(--input))] rounded-md bg-transparent";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[hsl(var(--background))] border border-[hsl(var(--border))] rounded-lg shadow-xl w-full max-w-6xl h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[hsl(var(--border))]">
          <h2 className="text-lg font-semibold">
            {isEditing ? "Edit Code Block" : "New Code Block"}
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-sm border border-[hsl(var(--border))] rounded-md hover:bg-[hsl(var(--accent))]"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!name || isSaving}
              className="px-4 py-1.5 text-sm bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 disabled:opacity-50"
            >
              {isSaving ? "Saving..." : isEditing ? "Save Changes" : "Create Block"}
            </button>
            <button onClick={onClose} className="p-1 hover:bg-[hsl(var(--accent))] rounded ml-1">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Body: two-column layout */}
        <div className="flex-1 flex min-h-0">
          {/* Left sidebar */}
          <div className="w-72 shrink-0 border-r border-[hsl(var(--border))] overflow-y-auto p-4 space-y-4">
            {/* Live node preview */}
            <NodePreview
              name={name}
              inputPorts={inputPorts}
              outputPorts={outputPorts}
            />

            <div className="border-t border-[hsl(var(--border))]" />

            {/* Name */}
            <div>
              <label className="block text-xs font-medium mb-1">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My Custom Block"
                className={inputClasses}
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-xs font-medium mb-1">Description</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What does this code do?"
                className={inputClasses}
              />
            </div>

            {/* Language */}
            <div>
              <label className="block text-xs font-medium mb-1">Language</label>
              <select
                value={language}
                onChange={(e) => handleLanguageChange(e.target.value as "python" | "javascript" | "bash")}
                className={`${inputClasses} bg-[hsl(var(--background))]`}
              >
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="bash">Bash</option>
              </select>
            </div>

            {/* Divider */}
            <div className="border-t border-[hsl(var(--border))]" />

            {/* Input Ports */}
            <PortBuilder
              label="Input Ports"
              ports={inputPorts}
              onChange={setInputPorts}
              direction="input"
            />

            {/* Divider */}
            <div className="border-t border-[hsl(var(--border))]" />

            {/* Output Ports */}
            <PortBuilder
              label="Output Ports"
              ports={outputPorts}
              onChange={setOutputPorts}
              direction="output"
            />

            {/* Divider */}
            <div className="border-t border-[hsl(var(--border))]" />

            {/* Tags */}
            <div>
              <label className="block text-xs font-medium mb-1">Tags</label>
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="network, enrichment, detection"
                className={inputClasses}
              />
            </div>

            {/* Public toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isPublic}
                onChange={(e) => setIsPublic(e.target.checked)}
                className="rounded border-[hsl(var(--input))]"
              />
              <span className="text-xs">Make public</span>
            </label>
          </div>

          {/* Right: code editor area */}
          <div className="flex-1 flex flex-col min-w-0">
            {/* Snippet toolbar */}
            <SnippetToolbar editorRef={editorRef} />

            {/* CodeMirror editor */}
            <div className="flex-1 min-h-0">
              <CodeEditorPane
                ref={editorRef}
                value={code}
                onChange={setCode}
                language={language}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

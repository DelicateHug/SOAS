/**
 * Panel showing the generated Python code from compile-preview.
 * Uses a simple <pre> with monospace font for syntax display.
 */

import { useGraphEditorStore } from "./stores/graphEditorStore";
import { Code2, Copy, Check } from "lucide-react";
import { useState, useCallback } from "react";

export function CodePreviewPanel() {
  const generatedCode = useGraphEditorStore((s) => s.generatedCode);
  const compilationWarnings = useGraphEditorStore(
    (s) => s.compilationWarnings
  );
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    if (!generatedCode) return;
    navigator.clipboard.writeText(generatedCode).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [generatedCode]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="flex items-center gap-2">
          <Code2 className="w-3.5 h-3.5" />
          <span className="text-xs font-semibold">Generated Code</span>
          {compilationWarnings.length > 0 && (
            <span className="text-[10px] text-yellow-500">
              {compilationWarnings.length} warning
              {compilationWarnings.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        {generatedCode && (
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-0.5 text-[10px] rounded hover:bg-[var(--color-surface-2)]"
            title="Copy to clipboard"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-green-500" />
                Copied
              </>
            ) : (
              <>
                <Copy className="w-3 h-3" />
                Copy
              </>
            )}
          </button>
        )}
      </div>

      {/* Code area */}
      <div className="flex-1 overflow-y-auto bg-gray-950 p-2">
        {/* Warnings */}
        {compilationWarnings.length > 0 && (
          <div className="mb-2 space-y-1">
            {compilationWarnings.map((warning, idx) => (
              <div
                key={idx}
                className="text-[10px] text-yellow-400 bg-yellow-900/20 px-2 py-1 rounded"
              >
                {warning.nodeId && (
                  <span className="font-medium">[{warning.nodeId}] </span>
                )}
                {warning.message}
              </div>
            ))}
          </div>
        )}

        {/* Code */}
        {generatedCode ? (
          <pre className="font-mono text-xs text-gray-200 whitespace-pre-wrap break-all leading-5">
            {generatedCode}
          </pre>
        ) : (
          <div className="text-gray-500 text-xs text-center py-4">
            Click "Compile" in the toolbar to generate Python code.
          </div>
        )}
      </div>
    </div>
  );
}

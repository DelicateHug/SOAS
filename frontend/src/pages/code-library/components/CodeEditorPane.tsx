/**
 * CodeMirror 6 editor wrapper component with syntax highlighting,
 * autocomplete, and snippet insertion support.
 */

import { useRef, useImperativeHandle, forwardRef } from "react";
import { useCodeMirror } from "../hooks/useCodeMirror";

export interface CodeEditorPaneHandle {
  insertAtCursor: (text: string) => void;
}

interface CodeEditorPaneProps {
  value: string;
  onChange: (value: string) => void;
  language: "python" | "javascript" | "bash";
}

export const CodeEditorPane = forwardRef<CodeEditorPaneHandle, CodeEditorPaneProps>(
  function CodeEditorPane({ value, onChange, language }, ref) {
    const containerRef = useRef<HTMLDivElement>(null);

    const { insertAtCursor } = useCodeMirror({
      container: containerRef,
      value,
      onChange,
      language,
    });

    useImperativeHandle(ref, () => ({
      insertAtCursor,
    }));

    return (
      <div
        ref={containerRef}
        className="h-full overflow-auto rounded-md border border-[var(--color-border)] [&_.cm-editor]:h-full [&_.cm-editor]:outline-none [&_.cm-scroller]:overflow-auto"
      />
    );
  }
);

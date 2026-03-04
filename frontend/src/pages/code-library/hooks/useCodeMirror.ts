/**
 * Custom React hook wrapping CodeMirror 6 EditorView.
 *
 * Provides syntax highlighting, dark theme, custom SOAS autocomplete,
 * and an insertAtCursor helper for snippet injection.
 */

import { useEffect, useRef, useCallback, type RefObject } from "react";
import { EditorState, Compartment, type Extension } from "@codemirror/state";
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { syntaxHighlighting, defaultHighlightStyle, bracketMatching, indentOnInput } from "@codemirror/language";
import { python } from "@codemirror/lang-python";
import { javascript } from "@codemirror/lang-javascript";
import { StreamLanguage } from "@codemirror/language";
import { shell } from "@codemirror/legacy-modes/mode/shell";
import { autocompletion, type CompletionContext, type CompletionResult } from "@codemirror/autocomplete";
import { searchKeymap, highlightSelectionMatches } from "@codemirror/search";
import { oneDark } from "@codemirror/theme-one-dark";

const languageCompartment = new Compartment();

function getLanguageExtension(lang: string): Extension {
  switch (lang) {
    case "python":
      return python();
    case "javascript":
      return javascript();
    case "bash":
      return StreamLanguage.define(shell);
    default:
      return python();
  }
}

/** Custom SOAS completion source for incident vars, SOAS vars, inputs/outputs */
function soasCompletions(context: CompletionContext): CompletionResult | null {
  const word = context.matchBefore(/[\w.]+/);
  if (!word && !context.explicit) return null;

  const from = word ? word.from : context.pos;

  return {
    from,
    options: [
      { label: "get_incident_var", type: "function", detail: "(name, default=None)", info: "Get an incident variable value" },
      { label: "set_incident_var", type: "function", detail: "(name, value)", info: "Set an incident variable" },
      { label: "get_incident_data", type: "function", detail: "()", info: "Get all incident metadata as dict" },
      { label: "get_soas_var", type: "function", detail: "(name, default=None)", info: "Get a SOAS application variable" },
      { label: "set_soas_var", type: "function", detail: "(name, value)", info: "Set a SOAS application variable" },
      { label: "inputs", type: "variable", detail: "dict", info: "Dictionary of input port values" },
      { label: "outputs", type: "variable", detail: "dict", info: "Dictionary to set output port values" },
      { label: "globals", type: "variable", detail: "dict", info: "Persistent global variable store across nodes" },
      { label: "print", type: "function", detail: "(value)", info: "Print debug output" },
    ],
  };
}

/** Custom dark theme that matches the SOAS app's CSS variables */
const soasDarkTheme = EditorView.theme(
  {
    "&": {
      backgroundColor: "hsl(222.2 84% 4.9%)",
      color: "hsl(210 40% 98%)",
      fontSize: "13px",
    },
    ".cm-content": {
      caretColor: "hsl(217.2 91.2% 59.8%)",
    },
    ".cm-cursor, .cm-dropCursor": {
      borderLeftColor: "hsl(217.2 91.2% 59.8%)",
    },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection":
      {
        backgroundColor: "hsl(217.2 32.6% 17.5%)",
      },
    ".cm-gutters": {
      backgroundColor: "hsl(222.2 84% 4.9%)",
      color: "hsl(215 20.2% 35%)",
      borderRight: "1px solid hsl(217.2 32.6% 12%)",
    },
    ".cm-activeLineGutter": {
      backgroundColor: "hsl(217.2 32.6% 10%)",
    },
    ".cm-activeLine": {
      backgroundColor: "hsl(217.2 32.6% 8%)",
    },
  },
  { dark: true }
);

interface UseCodeMirrorOptions {
  container: RefObject<HTMLDivElement | null>;
  value: string;
  onChange: (value: string) => void;
  language: "python" | "javascript" | "bash";
  extensions?: Extension[];
}

interface UseCodeMirrorReturn {
  view: EditorView | null;
  insertAtCursor: (text: string) => void;
}

export function useCodeMirror({
  container,
  value,
  onChange,
  language,
  extensions: extraExtensions = [],
}: UseCodeMirrorOptions): UseCodeMirrorReturn {
  const viewRef = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  // Track last cursor position so we can restore it for snippet insertions
  const lastCursorRef = useRef<number>(0);

  useEffect(() => {
    if (!container.current) return;

    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        onChangeRef.current(update.state.doc.toString());
      }
      // Track cursor position
      lastCursorRef.current = update.state.selection.main.head;
    });

    const state = EditorState.create({
      doc: value,
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        highlightActiveLineGutter(),
        drawSelection(),
        indentOnInput(),
        bracketMatching(),
        history(),
        highlightSelectionMatches(),
        syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
        languageCompartment.of(getLanguageExtension(language)),
        autocompletion({ override: [soasCompletions] }),
        keymap.of([...defaultKeymap, ...historyKeymap, ...searchKeymap]),
        oneDark,
        soasDarkTheme,
        updateListener,
        EditorView.lineWrapping,
        ...extraExtensions,
      ],
    });

    const view = new EditorView({
      state,
      parent: container.current,
    });

    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
    // Only recreate on mount — language changes handled via compartment
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [container]);

  // Update language when it changes
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    view.dispatch({
      effects: languageCompartment.reconfigure(getLanguageExtension(language)),
    });
  }, [language]);

  // Sync external value changes (e.g. template swap on language change)
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const currentDoc = view.state.doc.toString();
    if (currentDoc !== value) {
      view.dispatch({
        changes: { from: 0, to: currentDoc.length, insert: value },
      });
    }
  }, [value]);

  const insertAtCursor = useCallback((text: string) => {
    const view = viewRef.current;
    if (!view) return;

    // Use last known cursor position if editor is not focused
    const pos = view.hasFocus
      ? view.state.selection.main.head
      : lastCursorRef.current;

    view.dispatch({
      changes: { from: pos, insert: text },
      selection: { anchor: pos + text.length },
    });
    view.focus();
  }, []);

  return {
    view: viewRef.current,
    insertAtCursor,
  };
}

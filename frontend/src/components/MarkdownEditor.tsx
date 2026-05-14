import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Link from "@tiptap/extension-link";
import CodeBlockLowlight from "@tiptap/extension-code-block-lowlight";
import Image from "@tiptap/extension-image";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import { common, createLowlight } from "lowlight";
import { useEffect, useRef, useCallback } from "react";
import { cn } from "@/lib/utils";
import "./MarkdownEditor.css";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MarkdownEditorProps {
  /** HTML content to render in the editor */
  content: string;
  /** Called with the updated HTML whenever the document changes (debounced) */
  onChange: (html: string) => void;
  /** Placeholder text shown when the editor is empty */
  placeholder?: string;
  /** Whether the editor is editable (default true) */
  editable?: boolean;
  /** Extra class names applied to the outermost wrapper */
  className?: string;
}

// ---------------------------------------------------------------------------
// Lowlight instance (created once)
// ---------------------------------------------------------------------------

const lowlight = createLowlight(common);

// ---------------------------------------------------------------------------
// Toolbar button helper
// ---------------------------------------------------------------------------

interface ToolbarBtnProps {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  title: string;
  children: React.ReactNode;
}

function ToolbarBtn({
  onClick,
  active,
  disabled,
  title,
  children,
}: ToolbarBtnProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        "flex items-center justify-center rounded px-1.5 py-1 text-sm leading-none transition-colors",
        "hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text)]",
        "disabled:pointer-events-none disabled:opacity-40",
        active
          ? "bg-[var(--color-surface-2)] text-[var(--color-text)]"
          : "text-[var(--color-text-muted)]",
      )}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MarkdownEditor({
  content,
  onChange,
  placeholder = "Start writing...",
  editable = true,
  className,
}: MarkdownEditorProps) {
  // Stable onChange ref so we never re-create the editor when onChange changes
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const handleUpdate = useCallback(
    ({ editor }: { editor: ReturnType<typeof useEditor> extends infer E ? NonNullable<E> : never }) => {
      onChangeRef.current(editor.getHTML());
    },
    [],
  );

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        codeBlock: false, // replaced by CodeBlockLowlight
      }),
      Placeholder.configure({ placeholder }),
      Link.configure({
        openOnClick: false,
        autolink: true,
        linkOnPaste: true,
      }),
      CodeBlockLowlight.configure({ lowlight }),
      Image,
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
    ],
    content,
    editable,
    onUpdate: handleUpdate,
  });

  // Sync editable prop
  useEffect(() => {
    if (editor && editor.isEditable !== editable) {
      editor.setEditable(editable);
    }
  }, [editor, editable]);

  // Sync content when it changes externally (e.g. reset or load)
  const prevContentRef = useRef(content);
  useEffect(() => {
    if (editor && content !== prevContentRef.current) {
      const currentHtml = editor.getHTML();
      // Only update if the external content actually differs from what the
      // editor currently holds to avoid cursor-jump loops.
      if (content !== currentHtml) {
        editor.commands.setContent(content);
      }
      prevContentRef.current = content;
    }
  }, [editor, content]);


  if (!editor) return null;

  // ── Link toggle helper ─────────────────────────────────────────────
  const toggleLink = () => {
    if (editor.isActive("link")) {
      editor.chain().focus().unsetLink().run();
      return;
    }
    const url = window.prompt("URL:");
    if (url) {
      editor.chain().focus().setLink({ href: url }).run();
    }
  };

  // ── Insert table helper ────────────────────────────────────────────
  const insertTable = () => {
    editor
      .chain()
      .focus()
      .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
      .run();
  };

  return (
    <div
      className={cn(
        "rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]",
        "focus-within:ring-1 focus-within:ring-[var(--color-primary)]",
        className,
      )}
    >
      {/* ── Static Toolbar ──────────────────────────────────────────── */}
      {editable && (
        <div className="flex flex-wrap items-center gap-0.5 border-b border-[var(--color-border)] px-2 py-1">
          {/* Headings */}
          <ToolbarBtn
            onClick={() =>
              editor.chain().focus().toggleHeading({ level: 1 }).run()
            }
            active={editor.isActive("heading", { level: 1 })}
            title="Heading 1"
          >
            H1
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() =>
              editor.chain().focus().toggleHeading({ level: 2 }).run()
            }
            active={editor.isActive("heading", { level: 2 })}
            title="Heading 2"
          >
            H2
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() =>
              editor.chain().focus().toggleHeading({ level: 3 }).run()
            }
            active={editor.isActive("heading", { level: 3 })}
            title="Heading 3"
          >
            H3
          </ToolbarBtn>

          {/* Divider */}
          <div className="mx-1 h-4 w-px bg-[var(--color-border)]" />

          {/* Lists */}
          <ToolbarBtn
            onClick={() =>
              editor.chain().focus().toggleBulletList().run()
            }
            active={editor.isActive("bulletList")}
            title="Bullet List"
          >
            &#8226; List
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() =>
              editor.chain().focus().toggleOrderedList().run()
            }
            active={editor.isActive("orderedList")}
            title="Ordered List"
          >
            1. List
          </ToolbarBtn>

          {/* Divider */}
          <div className="mx-1 h-4 w-px bg-[var(--color-border)]" />

          {/* Block-level */}
          <ToolbarBtn
            onClick={() =>
              editor.chain().focus().toggleBlockquote().run()
            }
            active={editor.isActive("blockquote")}
            title="Blockquote"
          >
            &ldquo; Quote
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() =>
              editor.chain().focus().toggleCodeBlock().run()
            }
            active={editor.isActive("codeBlock")}
            title="Code Block"
          >
            {"<>"} Code
          </ToolbarBtn>
          <ToolbarBtn
            onClick={insertTable}
            title="Insert Table (3x3)"
          >
            &#9638; Table
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() =>
              editor.chain().focus().setHorizontalRule().run()
            }
            title="Horizontal Rule"
          >
            &#8212; HR
          </ToolbarBtn>
        </div>
      )}

      {/* ── Inline formatting toolbar ─────────────────────────────── */}
      {editable && (
        <div className="flex items-center gap-0.5 border-b border-[var(--color-border)] px-2 py-1">
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleBold().run()}
            active={editor.isActive("bold")}
            title="Bold"
          >
            <strong>B</strong>
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleItalic().run()}
            active={editor.isActive("italic")}
            title="Italic"
          >
            <em>I</em>
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleStrike().run()}
            active={editor.isActive("strike")}
            title="Strikethrough"
          >
            <s>S</s>
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleCode().run()}
            active={editor.isActive("code")}
            title="Inline Code"
          >
            {"<>"}
          </ToolbarBtn>
          <div className="mx-1 h-4 w-px bg-[var(--color-border)]" />
          <ToolbarBtn
            onClick={toggleLink}
            active={editor.isActive("link")}
            title="Link"
          >
            Link
          </ToolbarBtn>
        </div>
      )}

      {/* ── Editor Content ──────────────────────────────────────────── */}
      <EditorContent editor={editor} />
    </div>
  );
}

export default MarkdownEditor;

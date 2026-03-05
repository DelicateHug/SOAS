/**
 * Collaborative rich-text editor for wiki pages.
 * Uses Tiptap + Y.js for real-time simultaneous co-editing (Google Docs style).
 * Falls back to the regular MarkdownEditor when no collaboration is available.
 */

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
import Collaboration from "@tiptap/extension-collaboration";
import { common, createLowlight } from "lowlight";
import { useEffect, useRef } from "react";
import * as Y from "yjs";
import { cn } from "@/lib/utils";
import "@/components/MarkdownEditor.css";
import type { UseWikiCollaborationReturn, WikiCollaborator } from "./useWikiCollaboration";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CollaborativeMarkdownEditorProps {
  /** The Y.js collaboration context from useWikiCollaboration */
  collaboration: UseWikiCollaborationReturn;
  /** Current user display name for cursor labels */
  userName: string;
  /** Current user color for cursor */
  userColor: string;
  /** Placeholder text shown when the editor is empty */
  placeholder?: string;
  /** Whether the editor is editable (default true) */
  editable?: boolean;
  /** Extra class names applied to the outermost wrapper */
  className?: string;
  /** Called with the updated HTML whenever the document changes (debounced) */
  onChange?: (html: string) => void;
  /** HTML content to load into the editor (e.g. from a draft snapshot) */
  initialContent?: string;
}

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

const lowlight = createLowlight(common);

interface ToolbarBtnProps {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  title: string;
  children: React.ReactNode;
}

function ToolbarBtn({ onClick, active, disabled, title, children }: ToolbarBtnProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        "flex items-center justify-center rounded px-1.5 py-1 text-sm leading-none transition-colors",
        "hover:bg-[hsl(var(--accent))] hover:text-[hsl(var(--accent-foreground))]",
        "disabled:pointer-events-none disabled:opacity-40",
        active
          ? "bg-[hsl(var(--accent))] text-[hsl(var(--accent-foreground))]"
          : "text-[hsl(var(--muted-foreground))]"
      )}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Collaborator Avatars
// ---------------------------------------------------------------------------

function CollaboratorAvatars({ collaborators }: { collaborators: WikiCollaborator[] }) {
  if (collaborators.length === 0) return null;
  return (
    <div className="flex items-center gap-1">
      {collaborators.map((c) => (
        <div
          key={c.user_id}
          className="flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium text-white"
          style={{ backgroundColor: c.color }}
          title={c.display_name}
        >
          {c.display_name.charAt(0).toUpperCase()}
        </div>
      ))}
      <span className="ml-1 text-xs text-[hsl(var(--muted-foreground))]">
        {collaborators.length} editing
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CollaborativeMarkdownEditor({
  collaboration,
  userName: _userName,
  userColor: _userColor,
  placeholder = "Start writing...",
  editable = true,
  className,
  onChange,
  initialContent,
}: CollaborativeMarkdownEditorProps) {
  const { ydoc, collaborators, isConnected, broadcastUpdate, saveHtml } = collaboration;

  // Debounce ref for onChange / save
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  // Listen for Y.js document updates and broadcast them
  useEffect(() => {
    const handler = (update: Uint8Array, origin: unknown) => {
      // Only broadcast updates originating from this client (not remote applies)
      if (origin === "remote") return;
      const fullState = Y.encodeStateAsUpdate(ydoc);
      broadcastUpdate(update, fullState);
    };
    ydoc.on("update", handler);
    return () => {
      ydoc.off("update", handler);
    };
  }, [ydoc, broadcastUpdate]);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        codeBlock: false,
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
      Collaboration.configure({
        document: ydoc,
      }),
    ],
    editable,
    onUpdate: ({ editor: ed }) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        const html = ed.getHTML();
        if (onChangeRef.current) onChangeRef.current(html);
        // Persist HTML to backend
        saveHtml(html);
      }, 1000);
    },
  });

  // Load initial content (e.g. from draft snapshot) once the editor is ready
  const initialContentApplied = useRef(false);
  useEffect(() => {
    if (editor && initialContent && !initialContentApplied.current) {
      initialContentApplied.current = true;
      editor.commands.setContent(initialContent);
    }
  }, [editor, initialContent]);

  // Sync editable prop
  useEffect(() => {
    if (editor && editor.isEditable !== editable) {
      editor.setEditable(editable);
    }
  }, [editor, editable]);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  if (!editor) return null;

  // Link toggle
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

  // Insert table
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
        "rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))]",
        "focus-within:ring-1 focus-within:ring-[hsl(var(--ring))]",
        className
      )}
    >
      {/* Collaboration bar */}
      <div className="flex items-center justify-between border-b border-[hsl(var(--border))] px-3 py-1.5">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "h-2 w-2 rounded-full",
              isConnected ? "bg-green-500" : "bg-red-500"
            )}
            title={isConnected ? "Connected" : "Disconnected"}
          />
          <span className="text-xs text-[hsl(var(--muted-foreground))]">
            {isConnected ? "Live" : "Offline"}
          </span>
        </div>
        <CollaboratorAvatars collaborators={collaborators} />
      </div>

      {/* Block-level toolbar */}
      {editable && (
        <div className="flex flex-wrap items-center gap-0.5 border-b border-[hsl(var(--border))] px-2 py-1">
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            active={editor.isActive("heading", { level: 1 })}
            title="Heading 1"
          >
            H1
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            active={editor.isActive("heading", { level: 2 })}
            title="Heading 2"
          >
            H2
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            active={editor.isActive("heading", { level: 3 })}
            title="Heading 3"
          >
            H3
          </ToolbarBtn>
          <div className="mx-1 h-4 w-px bg-[hsl(var(--border))]" />
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            active={editor.isActive("bulletList")}
            title="Bullet List"
          >
            &#8226; List
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            active={editor.isActive("orderedList")}
            title="Ordered List"
          >
            1. List
          </ToolbarBtn>
          <div className="mx-1 h-4 w-px bg-[hsl(var(--border))]" />
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            active={editor.isActive("blockquote")}
            title="Blockquote"
          >
            &ldquo; Quote
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleCodeBlock().run()}
            active={editor.isActive("codeBlock")}
            title="Code Block"
          >
            {"<>"} Code
          </ToolbarBtn>
          <ToolbarBtn onClick={insertTable} title="Insert Table (3x3)">
            &#9638; Table
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() => editor.chain().focus().setHorizontalRule().run()}
            title="Horizontal Rule"
          >
            &#8212; HR
          </ToolbarBtn>
        </div>
      )}

      {/* Inline formatting toolbar */}
      {editable && (
        <div className="flex items-center gap-0.5 border-b border-[hsl(var(--border))] px-2 py-1">
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
          <div className="mx-1 h-4 w-px bg-[hsl(var(--border))]" />
          <ToolbarBtn onClick={toggleLink} active={editor.isActive("link")} title="Link">
            Link
          </ToolbarBtn>
        </div>
      )}

      {/* Editor Content */}
      <EditorContent editor={editor} />
    </div>
  );
}

export default CollaborativeMarkdownEditor;

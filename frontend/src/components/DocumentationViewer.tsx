import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import "@/components/MarkdownEditor.css";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TocEntry {
  id: string;
  text: string;
  level: number;
}

export interface DocumentationViewerProps {
  /** HTML content to render */
  content: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function slugify(text: string, index: number): string {
  const slug = text
    .toLowerCase()
    .replace(/[^\w]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || `heading-${index}`;
}

/** Parse HTML, add IDs to headings, and extract TOC entries. */
function processHtml(html: string): {
  processedHtml: string;
  headings: TocEntry[];
} {
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div>${html}</div>`, "text/html");
  const headingEls = doc.querySelectorAll("h1, h2, h3");
  const headings: TocEntry[] = [];
  const usedIds = new Set<string>();

  headingEls.forEach((el, i) => {
    const text = el.textContent?.trim() || "";
    let id = slugify(text, i);
    if (usedIds.has(id)) {
      id = `${id}-${i}`;
    }
    usedIds.add(id);
    el.setAttribute("id", id);
    headings.push({ id, text, level: parseInt(el.tagName[1]!) });
  });

  return {
    processedHtml: doc.body.firstElementChild?.innerHTML || html,
    headings,
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DocumentationViewer({ content }: DocumentationViewerProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [activeId, setActiveId] = useState<string>("");

  const { processedHtml, headings } = useMemo(
    () => processHtml(content),
    [content],
  );

  // Set initial active heading
  useEffect(() => {
    if (headings.length > 0 && !activeId && headings[0]) {
      setActiveId(headings[0].id);
    }
  }, [headings, activeId]);

  // Track active heading on scroll via IntersectionObserver
  useEffect(() => {
    if (headings.length === 0 || !contentRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
            break;
          }
        }
      },
      { rootMargin: "-80px 0px -80% 0px" },
    );

    headings.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [headings]);

  const scrollTo = useCallback((id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveId(id);
    }
  }, []);

  if (!content || content === "<p></p>") {
    return (
      <div className="text-center py-8 text-[hsl(var(--muted-foreground))]">
        No documentation yet. Switch to edit mode to start writing.
      </div>
    );
  }

  return (
    <div className="flex gap-6">
      {/* Content */}
      <div
        ref={contentRef}
        className="tiptap flex-1 min-w-0"
        dangerouslySetInnerHTML={{ __html: processedHtml }}
      />

      {/* TOC Sidebar */}
      {headings.length > 0 && (
        <nav className="w-48 shrink-0 sticky top-4 self-start max-h-[calc(100vh-6rem)] overflow-y-auto">
          <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider mb-2">
            On this page
          </p>
          <ul className="space-y-1 border-l border-[hsl(var(--border))]">
            {headings.map((h) => (
              <li key={h.id}>
                <button
                  onClick={() => scrollTo(h.id)}
                  className={`block w-full text-left text-sm py-0.5 transition-colors border-l-2 -ml-px ${
                    h.level === 1 ? "pl-3" : h.level === 2 ? "pl-5" : "pl-7"
                  } ${
                    activeId === h.id
                      ? "border-[hsl(var(--primary))] text-[hsl(var(--foreground))] font-medium"
                      : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] hover:border-[hsl(var(--border))]"
                  }`}
                >
                  {h.text}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </div>
  );
}

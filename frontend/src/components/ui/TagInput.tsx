import { useState, useRef, useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  allowDuplicates?: boolean;
}

export function TagInput({
  value,
  onChange,
  placeholder = "Add tags...",
  className,
  disabled = false,
  allowDuplicates = false,
}: TagInputProps) {
  const [inputValue, setInputValue] = useState("");
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const editInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingIndex !== null) {
      editInputRef.current?.focus();
      editInputRef.current?.select();
    }
  }, [editingIndex]);

  const canAddTag = (tag: string, ignoreIndex?: number): boolean => {
    if (!tag) return false;
    if (allowDuplicates) return true;
    return !value.some((t, i) => i !== ignoreIndex && t === tag);
  };

  const commitInput = () => {
    const trimmed = inputValue.trim();
    if (trimmed && canAddTag(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInputValue("");
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    if (raw.includes(",")) {
      const parts = raw.split(",");
      const newTags: string[] = [];
      for (let i = 0; i < parts.length - 1; i++) {
        const tag = parts[i]!.trim();
        if (tag && canAddTag(tag) && !newTags.includes(tag)) {
          newTags.push(tag);
        }
      }
      if (newTags.length > 0) {
        onChange([...value, ...newTags]);
      }
      setInputValue(parts[parts.length - 1] ?? "");
    } else {
      setInputValue(raw);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && inputValue === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
    if (e.key === "Enter") {
      e.preventDefault();
      commitInput();
    }
  };

  const removeTag = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const commitEdit = (index: number, newValue: string) => {
    const trimmed = newValue.trim();
    setEditingIndex(null);
    if (!trimmed) {
      removeTag(index);
      return;
    }
    if (!canAddTag(trimmed, index)) {
      return;
    }
    const updated = [...value];
    updated[index] = trimmed;
    onChange(updated);
    inputRef.current?.focus();
  };

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-1.5 px-2 py-1.5 rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] focus-within:ring-1 focus-within:ring-[var(--color-primary)] min-h-[38px] cursor-text",
        disabled && "opacity-50 cursor-not-allowed",
        className,
      )}
      onClick={() => {
        if (!disabled && editingIndex === null) {
          inputRef.current?.focus();
        }
      }}
    >
      {value.map((tag, index) => (
        <span
          key={`${index}-${tag}`}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-[var(--color-surface-2)] text-[var(--color-text)]"
        >
          {editingIndex === index ? (
            <input
              ref={editInputRef}
              defaultValue={tag}
              className="bg-transparent outline-none text-xs min-w-[20px]"
              style={{ width: `${Math.max(tag.length, 2)}ch` }}
              onBlur={(e) => commitEdit(index, e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  commitEdit(index, e.currentTarget.value);
                }
                if (e.key === "Escape") {
                  setEditingIndex(null);
                  inputRef.current?.focus();
                }
                e.stopPropagation();
              }}
              onChange={(e) => {
                e.target.style.width = `${Math.max(e.target.value.length, 2)}ch`;
              }}
              onClick={(e) => e.stopPropagation()}
              aria-label="Edit tag"
            />
          ) : (
            <>
              <button
                type="button"
                className="cursor-text"
                onClick={(e) => {
                  e.stopPropagation();
                  if (!disabled) setEditingIndex(index);
                }}
              >
                {tag}
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  if (!disabled) removeTag(index);
                }}
                className="hover:text-red-400 transition-colors"
                aria-label={`Remove ${tag}`}
              >
                <X className="w-3 h-3" />
              </button>
            </>
          )}
        </span>
      ))}
      <input
        ref={inputRef}
        type="text"
        value={inputValue}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        onBlur={commitInput}
        placeholder={value.length === 0 ? placeholder : ""}
        disabled={disabled}
        className="flex-1 min-w-[80px] bg-transparent outline-none text-sm placeholder:text-[var(--color-text-muted)]"
      />
    </div>
  );
}

import { useToastStore } from "@/stores/toastStore";
import { cn } from "@/lib/utils";

const TYPE_META = {
  success: {
    accent: "var(--color-success)",
    title: "Success",
    icon: (
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    ),
  },
  info: {
    accent: "var(--color-info)",
    title: "Working…",
    icon: (
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <circle cx="12" cy="12" r="10" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01" />
      </svg>
    ),
  },
  error: {
    accent: "var(--color-danger)",
    title: "Error",
    icon: (
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
  },
} as const;

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <>
      <style>{`
        @keyframes xs-toast-in {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2 max-w-sm">
        {toasts.map((t) => {
          const meta = TYPE_META[t.type];
          return (
            <div
              key={t.id}
              className={cn(
                "flex items-start gap-3 px-3.5 py-3 rounded-md shadow-lg",
                "bg-[var(--color-surface)] border border-[var(--color-border)]",
                "text-[var(--color-text)]",
              )}
              style={{
                borderLeft: `3px solid ${meta.accent}`,
                animation: "xs-toast-in 200ms ease-out",
              }}
            >
              <div
                className="shrink-0 w-5 h-5 mt-0.5"
                style={{ color: meta.accent }}
              >
                {meta.icon}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold">{meta.title}</p>
                <p className="text-xs mt-0.5 text-[var(--color-text-muted)]">{t.message}</p>
              </div>
              <button
                onClick={() => removeToast(t.id)}
                className="shrink-0 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                aria-label="Dismiss"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          );
        })}
      </div>
    </>
  );
}

import { useToastStore } from "@/stores/toastStore";

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-start gap-3 p-4 rounded-lg shadow-lg border ${
            t.type === "success"
              ? "bg-green-950 border-green-500/50 text-green-300"
              : t.type === "info"
              ? "bg-amber-950 border-amber-500/50 text-amber-300"
              : "bg-red-950 border-red-500/50 text-red-300"
          }`}
        >
          <div
            className={`shrink-0 w-5 h-5 mt-0.5 ${
              t.type === "success" ? "text-green-400" : t.type === "info" ? "text-amber-400" : "text-red-400"
            }`}
          >
            {t.type === "success" ? (
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            ) : t.type === "info" ? (
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01" />
                <circle cx="12" cy="12" r="10" strokeWidth={2} fill="none" />
              </svg>
            ) : (
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            )}
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium">
              {t.type === "success" ? "Success" : t.type === "info" ? "Working..." : "Error"}
            </p>
            <p className="text-xs mt-1 opacity-80">{t.message}</p>
          </div>
          <button onClick={() => removeToast(t.id)} className="shrink-0 opacity-60 hover:opacity-100">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}

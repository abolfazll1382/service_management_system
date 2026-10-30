"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { CheckCircle2, X, XCircle } from "lucide-react";
import { createId } from "@/lib/utils/id";
import { cn } from "@/lib/utils/cn";
import { useT } from "./LocaleProvider";

type ToastVariant = "success" | "error";

interface Toast {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const LIFETIME_MS = 5000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const t = useT();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: string) => {
    const timer = timers.current.get(id);
    if (timer) clearTimeout(timer);
    timers.current.delete(id);
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback(
    (variant: ToastVariant, message: string) => {
      const id = createId();
      setToasts((current) => [...current, { id, message, variant }]);
      timers.current.set(id, setTimeout(() => dismiss(id), LIFETIME_MS));
    },
    [dismiss],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach((timer) => clearTimeout(timer));
  }, []);

  const api = useMemo<ToastApi>(
    () => ({ success: (message) => show("success", message), error: (message) => show("error", message) }),
    [show],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 top-4 z-[100] flex flex-col items-center gap-2 px-4">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            // Errors interrupt a screen reader; confirmations wait their turn.
            role={toast.variant === "error" ? "alert" : "status"}
            className={cn(
              "pointer-events-auto flex w-full max-w-sm items-center gap-3 rounded-lg border bg-white p-3.5 text-sm",
              toast.variant === "success" ? "border-emerald-300 text-emerald-900" : "border-rose-300 text-rose-900",
            )}
          >
            {toast.variant === "success" ? (
              <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" aria-hidden="true" />
            ) : (
              <XCircle className="h-5 w-5 shrink-0 text-rose-600" aria-hidden="true" />
            )}
            <p className="flex-1 font-medium">{toast.message}</p>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              aria-label={t("common.toast.dismiss")}
              className="rounded p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-700"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used within a ToastProvider");
  return context;
}

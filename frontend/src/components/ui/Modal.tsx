"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useT } from "@/providers/LocaleProvider";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}

const SIZE_STYLES = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
} as const;

/**
 * Built on the native <dialog>: the browser traps focus inside, makes the
 * rest of the page inert, closes on Escape and restores focus afterwards —
 * the parts a hand-rolled modal usually gets subtly wrong. Content mounts
 * only while open, so a form inside always starts fresh.
 */
export function Modal({ isOpen, onClose, title, children, size = "md" }: ModalProps) {
  const t = useT();
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (isOpen && !dialog.open) dialog.showModal();
    if (!isOpen && dialog.open) dialog.close();
  }, [isOpen]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={title ? titleId : undefined}
      onClose={onClose}
      // A click on the dim area lands on the <dialog> itself (the panel inside is a child).
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
      className={cn(
        "m-auto w-[calc(100%-2rem)] rounded-xl border border-ink-200 bg-white p-0 text-ink-900",
        "max-h-[calc(100dvh-2rem)] overflow-y-auto",
        SIZE_STYLES[size],
      )}
    >
      {isOpen && (
        <div className="p-5 sm:p-6">
          <div className="mb-4 flex items-start justify-between gap-4">
            {title ? (
              <h2 id={titleId} className="text-lg font-semibold text-ink-900">
                {title}
              </h2>
            ) : (
              <span />
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label={t("common.actions.close")}
              className="shrink-0 rounded-md p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-700"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}

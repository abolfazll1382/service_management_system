import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

const TONE_STYLES = {
  neutral: "bg-ink-100 text-ink-700",
  info: "bg-sky-100 text-sky-900",
  success: "bg-emerald-100 text-emerald-900",
  warning: "bg-amber-100 text-amber-900",
  danger: "bg-rose-100 text-rose-900",
  attention: "bg-saffron-100 text-saffron-700",
  closed: "bg-ink-200 text-ink-600",
} as const;

export type BadgeTone = keyof typeof TONE_STYLES;

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

/** A small label. Meaning lives in the text, never in colour alone. */
export function Badge({ tone = "neutral", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap", TONE_STYLES[tone], className)}
      {...props}
    />
  );
}

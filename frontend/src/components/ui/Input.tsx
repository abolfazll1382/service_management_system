import { type InputHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils/cn";

/** Shared look for text-like controls (Input, Select, Textarea). */
export function controlStyles(invalid?: boolean) {
  return cn(
    "w-full rounded-lg border bg-white text-sm text-ink-900",
    "placeholder:text-ink-400",
    "transition-colors duration-150",
    "focus:outline-none focus:ring-2",
    invalid
      ? "border-rose-400 focus:border-rose-500 focus:ring-rose-200"
      : "border-ink-200 hover:border-ink-300 focus:border-tile-600 focus:ring-tile-200",
    "disabled:cursor-not-allowed disabled:bg-ink-50 disabled:text-ink-400",
  );
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
  /**
   * For IDs, phone numbers and amounts: digits stay left-to-right on a
   * right-to-left page (see `input[data-numeric]` in globals.css) and phones
   * get the numeric keypad on mobile.
   */
  numeric?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, invalid, numeric, ...props }, ref) => (
  <input
    ref={ref}
    aria-invalid={invalid || undefined}
    data-numeric={numeric ? "" : undefined}
    inputMode={numeric ? "numeric" : undefined}
    autoComplete={props.autoComplete ?? "off"}
    className={cn(controlStyles(invalid), "h-10 px-3", className)}
    {...props}
  />
));
Input.displayName = "Input";

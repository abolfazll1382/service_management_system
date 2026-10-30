import { type ButtonHTMLAttributes, forwardRef } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const VARIANT_STYLES = {
  primary: "bg-tile-700 text-white hover:bg-tile-800",
  secondary: "bg-ink-100 text-ink-900 hover:bg-ink-200",
  outline: "border border-ink-200 bg-white text-ink-800 hover:border-ink-300 hover:bg-ink-50",
  ghost: "text-ink-700 hover:bg-ink-100",
  danger: "bg-rose-700 text-white hover:bg-rose-800",
} as const;

const SIZE_STYLES = {
  sm: "h-8 px-3 text-sm gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-12 px-6 text-base gap-2",
} as const;

export type ButtonVariant = keyof typeof VARIANT_STYLES;
export type ButtonSize = keyof typeof SIZE_STYLES;

interface StyleOptions {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  className?: string;
}

/**
 * The button look as a function, so a Next.js <Link> can wear it too:
 * `<Link className={buttonStyles({ variant: "outline" })}>`. A link that
 * navigates must be an anchor, not a <button> inside one.
 */
export function buttonStyles({ variant = "primary", size = "md", fullWidth = false, className }: StyleOptions = {}) {
  return cn(
    "inline-flex items-center justify-center rounded-lg font-medium whitespace-nowrap",
    "transition-colors duration-150",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tile-600",
    "disabled:cursor-not-allowed disabled:opacity-50",
    VARIANT_STYLES[variant],
    SIZE_STYLES[size],
    fullWidth && "w-full",
    className,
  );
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, StyleOptions {
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, fullWidth, isLoading = false, disabled, type = "button", children, ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      className={buttonStyles({ variant, size, fullWidth, className })}
      {...props}
    >
      {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  ),
);
Button.displayName = "Button";

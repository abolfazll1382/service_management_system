import { type SelectHTMLAttributes, forwardRef } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { controlStyles } from "./Input";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean;
}

/**
 * A styled native <select>. The chevron and its padding use LOGICAL
 * properties (`pe-9`, `end-3`), so "end" is the right edge in English and
 * the left edge in Persian — the arrow follows the reading direction
 * instead of being pinned to one physical side.
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(({ className, invalid, children, ...props }, ref) => (
  <div className="relative">
    <select
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(controlStyles(invalid), "h-10 appearance-none ps-3 pe-9", className)}
      {...props}
    >
      {children}
    </select>
    <ChevronDown
      className="pointer-events-none absolute end-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
      aria-hidden="true"
    />
  </div>
));
Select.displayName = "Select";

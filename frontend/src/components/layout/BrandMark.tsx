import { cn } from "@/lib/utils/cn";

/**
 * The portal's own mark: an eight-pointed star built from two squares, the
 * basic move of geometric tilework. Deliberately generic — it is not, and
 * must not resemble, any real institution's emblem.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("h-9 w-9 shrink-0", className)} aria-hidden="true">
      <rect width="32" height="32" rx="8" className="fill-ink-900" />
      <g fill="none" strokeWidth="1.6" strokeLinejoin="round" className="stroke-tile-300">
        <rect x="9.5" y="9.5" width="13" height="13" />
        <rect x="9.5" y="9.5" width="13" height="13" transform="rotate(45 16 16)" />
      </g>
    </svg>
  );
}

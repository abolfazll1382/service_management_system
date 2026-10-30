import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

/**
 * Isolates a run of text that must read left-to-right inside right-to-left
 * prose: tracking codes, phone numbers, national IDs, usernames. Without it
 * the bidi algorithm can reorder the punctuation around them.
 */
export function Ltr({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span dir="ltr" className={cn("inline-block tabular-nums [unicode-bidi:isolate]", className)} {...props} />;
}

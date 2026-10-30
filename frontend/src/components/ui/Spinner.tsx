"use client";

import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useT } from "@/providers/LocaleProvider";

export function Spinner({ className }: { className?: string }) {
  const t = useT();
  return (
    <span role="status" className="inline-flex">
      <Loader2 className={cn("h-5 w-5 animate-spin text-tile-700", className)} aria-hidden="true" />
      <span className="sr-only">{t("common.state.loading")}</span>
    </span>
  );
}

/** A centred spinner for a region that is waiting on data. */
export function LoadingBlock({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center justify-center py-16", className)}>
      <Spinner className="h-6 w-6" />
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-md bg-ink-100", className)} />;
}

"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Ltr } from "@/components/ui/Ltr";
import { cn } from "@/lib/utils/cn";
import { useFormat, useT } from "@/providers/LocaleProvider";

/**
 * The reference number a customer quotes to staff. Shown with digits in the
 * active script, but COPIED as plain ASCII so it pastes into any search box.
 */
export function TrackingCode({ code, className, large }: { code: string; className?: string; large?: boolean }) {
  const t = useT();
  const format = useFormat();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be denied (insecure origin, permissions); the code stays selectable on screen.
    }
  };

  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <Ltr className={cn("font-semibold tracking-wider text-ink-950", large ? "text-2xl" : "text-sm")}>{format.digits(code)}</Ltr>
      <button
        type="button"
        onClick={copy}
        title={copied ? t("common.actions.copied") : t("request.detail.copyCode")}
        aria-label={t("request.detail.copyCode")}
        className="rounded-md p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-700 focus-visible:outline-2 focus-visible:outline-tile-600"
      >
        {copied ? <Check className="h-4 w-4 text-emerald-600" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
      </button>
    </span>
  );
}

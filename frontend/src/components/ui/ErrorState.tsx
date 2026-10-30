"use client";

import { RefreshCw } from "lucide-react";
import { useT } from "@/providers/LocaleProvider";
import { Alert } from "./Alert";
import { Button } from "./Button";

/** What went wrong, and a way to try again. */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const t = useT();
  return (
    <div className="flex flex-col items-start gap-3">
      <Alert tone="danger" className="w-full">
        {message}
      </Alert>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          {t("common.actions.retry")}
        </Button>
      )}
    </div>
  );
}

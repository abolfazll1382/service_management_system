"use client";

import { useCallback } from "react";
import { useT } from "@/providers/LocaleProvider";
import { ApiError } from "@/types/api";

/**
 * Turns whatever was thrown into text in the active language. API errors
 * carry a stable code; anything else (a bug) gets the generic message.
 */
export function useErrorMessage() {
  const t = useT();
  return useCallback((error: unknown): string => (error instanceof ApiError ? t(`errors.${error.code}`) : t("errors.unknown")), [t]);
}

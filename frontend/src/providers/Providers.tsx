"use client";

import type { ReactNode } from "react";
import type { Locale } from "@/types/i18n";
import { AuthProvider } from "./AuthProvider";
import { LocaleProvider } from "./LocaleProvider";
import { ToastProvider } from "./ToastProvider";

/** One place that lists every app-wide provider and their nesting order. */
export function Providers({ locale, children }: { locale: Locale; children: ReactNode }) {
  return (
    <LocaleProvider initialLocale={locale}>
      <ToastProvider>
        <AuthProvider>{children}</AuthProvider>
      </ToastProvider>
    </LocaleProvider>
  );
}

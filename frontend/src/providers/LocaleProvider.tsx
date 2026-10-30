"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { LOCALE_COOKIE, LOCALE_DIR } from "@/lib/i18n/config";
import { formatDate, formatDateTime, formatDigits, formatNumber } from "@/lib/i18n/format";
import { createTranslator } from "@/lib/i18n/translate";
import type { Translate } from "@/lib/i18n/types";
import type { Locale } from "@/types/i18n";

interface LocaleContextValue {
  locale: Locale;
  dir: "rtl" | "ltr";
  t: Translate;
  setLocale: (next: Locale) => void;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

/**
 * Holds the active language. The server decides the FIRST paint (it reads the
 * cookie in the root layout and renders the right `lang`/`dir`), so there is
 * no flash of the wrong language or direction. Switching afterwards:
 *
 *  1. writes the cookie, so the next request — and the server — agree;
 *  2. flips `lang`/`dir` on <html> immediately, so the layout mirrors now;
 *  3. updates React state, so every `t()` call re-renders in the new language;
 *  4. `router.refresh()` re-renders server components (page titles, layout).
 */
export function LocaleProvider({ initialLocale, children }: { initialLocale: Locale; children: ReactNode }) {
  const router = useRouter();
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const t = useMemo(() => createTranslator(locale), [locale]);

  const setLocale = useCallback(
    (next: Locale) => {
      if (next === locale) return;
      document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${ONE_YEAR_SECONDS}; samesite=lax`;
      document.documentElement.lang = next;
      document.documentElement.dir = LOCALE_DIR[next];
      setLocaleState(next);
      router.refresh();
    },
    [locale, router],
  );

  const value = useMemo<LocaleContextValue>(
    () => ({ locale, dir: LOCALE_DIR[locale], t, setLocale }),
    [locale, t, setLocale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

function useLocaleContext(): LocaleContextValue {
  const context = useContext(LocaleContext);
  if (!context) throw new Error("useLocale/useT must be used within a LocaleProvider");
  return context;
}

export function useLocale() {
  const { locale, dir, setLocale } = useLocaleContext();
  return { locale, dir, setLocale };
}

/** The translator for the active language: `t("common.actions.save")`. */
export function useT(): Translate {
  return useLocaleContext().t;
}

/** Date/number formatters bound to the active language (Jalali + Persian digits in fa). */
export function useFormat() {
  const { locale } = useLocaleContext();
  return useMemo(
    () => ({
      date: (iso: string) => formatDate(iso, locale),
      dateTime: (iso: string) => formatDateTime(iso, locale),
      number: (value: number) => formatNumber(value, locale),
      digits: (value: string) => formatDigits(value, locale),
    }),
    [locale],
  );
}

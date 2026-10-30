import { LOCALES, type Locale } from "@/types/i18n";

export const DEFAULT_LOCALE: Locale = "fa";

/** Persisted choice. Read on the server (root layout) so first paint is right. */
export const LOCALE_COOKIE = "portal-locale";

export const LOCALE_DIR: Record<Locale, "rtl" | "ltr"> = {
  fa: "rtl",
  en: "ltr",
};

/** BCP 47 tags for Intl. `fa-IR` implies the Jalali calendar and Persian digits. */
export const INTL_LOCALE: Record<Locale, string> = {
  fa: "fa-IR",
  en: "en-US",
};

export function isLocale(value: string | undefined): value is Locale {
  return LOCALES.some((locale) => locale === value);
}

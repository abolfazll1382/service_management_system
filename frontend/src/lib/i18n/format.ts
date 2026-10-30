import type { Locale } from "@/types/i18n";
import { toPersianDigits } from "@/lib/utils/persianUtils";
import { INTL_LOCALE } from "./config";

/**
 * Intl formatters are comparatively expensive to construct, and their options
 * never change, so each (locale, kind) pair is built once and cached.
 */
const dateFormatters = new Map<Locale, Intl.DateTimeFormat>();
const dateTimeFormatters = new Map<Locale, Intl.DateTimeFormat>();
const numberFormatters = new Map<Locale, Intl.NumberFormat>();

function cached<T>(cache: Map<Locale, T>, locale: Locale, create: () => T): T {
  const hit = cache.get(locale);
  if (hit) return hit;
  const created = create();
  cache.set(locale, created);
  return created;
}

/** fa → Jalali calendar ("۲۱ مهر ۱۴۰۵"); en → Gregorian ("Oct 13, 2026"). */
export function formatDate(iso: string, locale: Locale): string {
  return cached(
    dateFormatters,
    locale,
    () =>
      new Intl.DateTimeFormat(INTL_LOCALE[locale], {
        year: "numeric",
        month: locale === "fa" ? "long" : "short",
        day: "numeric",
      }),
  ).format(new Date(iso));
}

export function formatDateTime(iso: string, locale: Locale): string {
  return cached(
    dateTimeFormatters,
    locale,
    () =>
      new Intl.DateTimeFormat(INTL_LOCALE[locale], {
        year: "numeric",
        month: locale === "fa" ? "long" : "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }),
  ).format(new Date(iso));
}

export function formatNumber(value: number, locale: Locale): string {
  return cached(numberFormatters, locale, () => new Intl.NumberFormat(INTL_LOCALE[locale])).format(value);
}

/** Digit-string display (codes, phone numbers): Persian digits only in fa. */
export function formatDigits(value: string, locale: Locale): string {
  return locale === "fa" ? toPersianDigits(value) : value;
}

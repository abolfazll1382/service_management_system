/**
 * Locale primitives. This is the lowest layer of the project, so it must
 * not import from anywhere else. `Localized` is how DOMAIN content (service
 * titles, staff display names) carries its own translations, while UI chrome
 * (buttons, labels, errors) lives in the dictionaries under lib/i18n.
 * Splitting the two keeps the dictionaries small and lets an admin-managed
 * catalog be translated without touching code.
 */
export const LOCALES = ["fa", "en"] as const;
export type Locale = (typeof LOCALES)[number];

export type Localized = Readonly<Record<Locale, string>>;

/** For user-entered text (a customer's own name) that has no translation. */
export function localizedFromPlain(value: string): Localized {
  return { fa: value, en: value };
}

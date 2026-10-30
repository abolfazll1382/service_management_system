import { cookies } from "next/headers";
import type { Locale } from "@/types/i18n";
import { DEFAULT_LOCALE, LOCALE_COOKIE, isLocale } from "./config";
import { createTranslator } from "./translate";

/**
 * Server-side locale, read from the cookie the language toggle writes.
 * Reading it in the root layout is what makes first paint correct (right
 * `dir`, right language) with no flash — the alternative, localStorage, is
 * invisible to the server and always flashes the default language first.
 */
export async function getServerLocale(): Promise<Locale> {
  const store = await cookies();
  const value = store.get(LOCALE_COOKIE)?.value;
  return isLocale(value) ? value : DEFAULT_LOCALE;
}

export async function getServerT() {
  return createTranslator(await getServerLocale());
}

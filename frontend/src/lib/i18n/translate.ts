import type { Locale } from "@/types/i18n";
import { en } from "./dictionaries/en";
import { fa } from "./dictionaries/fa";
import { formatNumber } from "./format";
import type { Dictionary, Translate, TranslationKey, TranslationParams } from "./types";

export const DICTIONARIES: Record<Locale, Dictionary> = { en, fa };

function lookup(dictionary: Dictionary, key: TranslationKey): string {
  let node: unknown = dictionary;
  for (const part of key.split(".")) {
    if (typeof node !== "object" || node === null) return key;
    node = (node as Record<string, unknown>)[part];
  }
  // Falling back to the key (not "") makes a gap visible instead of silent.
  return typeof node === "string" ? node : key;
}

/**
 * `{name}` placeholders. Numbers are formatted for the active locale, so
 * `{days}` renders "۵" in Persian and "5" in English without callers caring.
 */
function interpolate(template: string, params: TranslationParams | undefined, locale: Locale): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) => {
    const value = params[name];
    if (value === undefined) return match;
    return typeof value === "number" ? formatNumber(value, locale) : value;
  });
}

export function createTranslator(locale: Locale): Translate {
  const dictionary = DICTIONARIES[locale];
  return (key, params) => interpolate(lookup(dictionary, key), params, locale);
}

/** Flattens a dictionary into dotted keys — used by the parity test. */
export function flattenKeys(node: unknown, prefix = ""): string[] {
  if (typeof node === "string") return [prefix];
  if (typeof node !== "object" || node === null) return [];
  return Object.entries(node).flatMap(([key, value]) => flattenKeys(value, prefix ? `${prefix}.${key}` : key));
}

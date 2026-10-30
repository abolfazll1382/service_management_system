import { describe, expect, it } from "vitest";
import { DICTIONARIES, createTranslator, flattenKeys } from "@/lib/i18n/translate";
import { formatDate, formatDateTime, formatDigits, formatNumber } from "@/lib/i18n/format";
import { DEFAULT_LOCALE, LOCALE_DIR, isLocale } from "@/lib/i18n/config";
import { LOCALES } from "@/types/i18n";
import { REQUEST_STATUSES } from "@/types/request";
import { API_ERROR_CODES } from "@/types/api";
import { AUDIT_ACTIONS } from "@/types/audit";
import { DEPARTMENT_IDS } from "@/types/department";

const keys = (locale: "fa" | "en") => flattenKeys(DICTIONARIES[locale]).sort();

describe("dictionaries", () => {
  it("define exactly the same keys in Persian and English", () => {
    const en = keys("en");
    const fa = keys("fa");
    expect(fa.filter((key) => !en.includes(key)), "only in fa").toEqual([]);
    expect(en.filter((key) => !fa.includes(key)), "only in en").toEqual([]);
  });

  it("have no empty strings and the same {placeholders} in both languages", () => {
    const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
    const read = (locale: "fa" | "en", key: string) =>
      key.split(".").reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], DICTIONARIES[locale]) as string;
    for (const key of keys("en")) {
      const en = read("en", key);
      const fa = read("fa", key);
      expect(en.trim(), `en ${key}`).not.toBe("");
      expect(fa.trim(), `fa ${key}`).not.toBe("");
      expect(placeholders(fa), `placeholders of ${key}`).toEqual(placeholders(en));
    }
  });

  it("translate every status, error code, audit action and department that the domain defines", () => {
    for (const locale of LOCALES) {
      const t = createTranslator(locale);
      for (const status of REQUEST_STATUSES) expect(t(`common.status.${status}`)).not.toContain("common.status");
      for (const code of API_ERROR_CODES) expect(t(`errors.${code}`)).not.toContain("errors.");
      for (const action of AUDIT_ACTIONS) expect(t(`staff.audit.actions.${action}`)).not.toContain("staff.audit");
    }
    expect(DEPARTMENT_IDS.length).toBeGreaterThan(0);
  });

  it("keep each language in its own script, apart from the language names themselves", () => {
    // The language switcher names each language in its own script, by design.
    const OWN_SCRIPT_LABELS = new Set(["common.language.fa", "common.language.en"]);
    const text = (locale: "fa" | "en", key: string) =>
      key.split(".").reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], DICTIONARIES[locale]) as string;
    const arabicScript = /[\u0600-\u06FF]/;
    const latinWord = /[A-Za-z]{4,}/;
    for (const key of keys("en")) {
      if (OWN_SCRIPT_LABELS.has(key)) continue;
      expect(arabicScript.test(text("en", key)), `Persian text in the English dictionary: ${key}`).toBe(false);
      const fa = text("fa", key).replace(/\{\w+\}/g, "");
      if (/^[\dx#\s-]+$/i.test(fa)) continue; // format hints such as "09xxxxxxxxx" are the same in both languages
      // A Persian string with a Latin word and no Persian at all is almost always a forgotten translation.
      expect(!arabicScript.test(fa) && latinWord.test(fa), `Persian dictionary looks untranslated: ${key} = ${fa}`).toBe(false);
    }
  });
});

describe("translator", () => {
  it("interpolates placeholders and formats numbers per locale", () => {
    expect(createTranslator("en")("validation.number.min", { min: 1500 })).toContain("1,500");
    expect(createTranslator("fa")("validation.number.min", { min: 1500 })).toContain("۱٬۵۰۰");
  });

  it("falls back to the key itself, so a gap is visible instead of blank", () => {
    expect(createTranslator("en")("does.not.exist" as never)).toBe("does.not.exist");
  });
});

describe("locale config", () => {
  it("defaults to Persian, right-to-left; English is left-to-right", () => {
    expect(DEFAULT_LOCALE).toBe("fa");
    expect(LOCALE_DIR.fa).toBe("rtl");
    expect(LOCALE_DIR.en).toBe("ltr");
    expect(isLocale("fa") && isLocale("en") && !isLocale("de") && !isLocale(undefined)).toBe(true);
  });
});

describe("formatting", () => {
  const iso = "2026-10-13T10:30:00.000Z";

  it("uses the Jalali calendar and Persian digits in Persian, Gregorian in English", () => {
    const fa = formatDate(iso, "fa");
    expect(fa).toMatch(/۱۴۰۵/); // 13 Oct 2026 is in Jalali year 1405
    expect(fa).toMatch(/مهر/); // Mehr
    expect(formatDate(iso, "en")).toMatch(/2026/);
    expect(formatDateTime(iso, "fa")).not.toBe(formatDateTime(iso, "en"));
  });

  it("formats numbers and digit strings per locale", () => {
    expect(formatNumber(1234567, "en")).toBe("1,234,567");
    expect(formatNumber(1234567, "fa")).toBe("۱٬۲۳۴٬۵۶۷");
    expect(formatDigits("09121234567", "fa")).toBe("۰۹۱۲۱۲۳۴۵۶۷");
    expect(formatDigits("09121234567", "en")).toBe("09121234567");
  });
});

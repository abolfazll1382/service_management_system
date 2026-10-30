"use client";

import { cn } from "@/lib/utils/cn";
import { LOCALES } from "@/types/i18n";
import { useLocale, useT } from "@/providers/LocaleProvider";

/**
 * Persian ⇄ English. Each button names its language in that language's own
 * script (and carries the matching `lang`), so someone who can't read the
 * current page can still find theirs. Switching mirrors the whole layout.
 */
export function LanguageToggle({ className }: { className?: string }) {
  const { locale, setLocale } = useLocale();
  const t = useT();
  return (
    <div role="group" aria-label={t("common.language.label")} className={cn("inline-flex rounded-lg border border-ink-200 bg-white p-0.5", className)}>
      {LOCALES.map((code) => {
        const active = locale === code;
        return (
          <button
            key={code}
            type="button"
            lang={code}
            aria-pressed={active}
            onClick={() => setLocale(code)}
            className={cn(
              "rounded-md px-2.5 py-1 text-sm font-medium transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-tile-600",
              active ? "bg-ink-900 text-white" : "text-ink-600 hover:bg-ink-100 hover:text-ink-900",
            )}
          >
            {t(`common.language.${code}`)}
          </button>
        );
      })}
    </div>
  );
}

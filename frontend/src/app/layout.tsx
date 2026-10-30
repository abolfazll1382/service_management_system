import type { Metadata } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";
import { LOCALE_DIR } from "@/lib/i18n/config";
import { getServerLocale, getServerT } from "@/lib/i18n/server";
import { Providers } from "@/providers/Providers";
import "./globals.css";

/**
 * Vazirmatn, self-hosted via next/font/local: the font file ships from your
 * own domain (no third-party request, no layout shift) and is vendored into
 * the repo from the `vazirmatn` npm package, so builds work offline. One
 * variable-weight file covers every weight, and it includes Latin glyphs, so
 * the English interface uses the same face.
 *
 * The file is named without square brackets (the package calls it
 * `Vazirmatn[wght].woff2`): next/font writes the brackets percent-encoded in
 * the preload tag but raw in the CSS, so the browser sees two different URLs
 * and warns that the preloaded font was never used.
 */
const vazirmatn = localFont({
  src: "./fonts/Vazirmatn-Variable.woff2",
  variable: "--font-vazirmatn",
  weight: "100 900",
  display: "swap",
});

export async function generateMetadata(): Promise<Metadata> {
  const t = await getServerT();
  return {
    title: { default: t("common.brand.name"), template: `%s | ${t("common.brand.short")}` },
    description: t("catalog.hero.subtitle"),
  };
}

// Typed by hand rather than with Next's generated `LayoutProps<'/'>`, which only
// exists after a first `next dev`/`next build` — this works on a fresh clone.
export default async function RootLayout({ children }: { children: ReactNode }) {
  // The language is a cookie, so the server renders the right `lang` and `dir`
  // on the very first byte — no flash of the wrong language or direction.
  const locale = await getServerLocale();
  return (
    <html lang={locale} dir={LOCALE_DIR[locale]} className={vazirmatn.variable}>
      <body className="flex min-h-dvh flex-col">
        <Providers locale={locale}>{children}</Providers>
      </body>
    </html>
  );
}

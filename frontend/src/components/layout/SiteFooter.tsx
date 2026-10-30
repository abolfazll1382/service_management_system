"use client";

import Link from "next/link";
import { useT } from "@/providers/LocaleProvider";
import { BrandMark } from "./BrandMark";

export function SiteFooter() {
  const t = useT();
  return (
    <footer className="mt-auto border-t border-ink-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 sm:flex-row sm:items-start sm:justify-between sm:px-6">
        <div className="flex max-w-xl items-start gap-3">
          <BrandMark className="h-8 w-8" />
          <div>
            <p className="text-sm font-semibold text-ink-900">{t("common.brand.name")}</p>
            <p className="mt-1 text-sm text-ink-600">{t("common.footer.demo")}</p>
          </div>
        </div>
        <Link href="/console/login" className="text-sm font-medium text-ink-700 underline-offset-4 hover:text-ink-950 hover:underline">
          {t("common.nav.staffSignIn")}
        </Link>
      </div>
    </footer>
  );
}

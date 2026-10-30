import Link from "next/link";
import { BrandMark } from "@/components/layout/BrandMark";
import { buttonStyles } from "@/components/ui/Button";
import { getServerT } from "@/lib/i18n/server";

/** The 404 page, in the visitor's language (the default one is English-only). */
export default async function NotFound() {
  const t = await getServerT();
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 px-6 text-center">
      <BrandMark className="h-12 w-12" />
      <div>
        <p className="text-sm font-semibold text-tile-700">{t("common.notFound.code")}</p>
        <h1 className="mt-1 text-2xl font-bold text-ink-950">{t("common.notFound.title")}</h1>
        <p className="mx-auto mt-1.5 max-w-md text-sm text-ink-600">{t("common.notFound.body")}</p>
      </div>
      <Link href="/" className={buttonStyles()}>
        {t("common.notFound.home")}
      </Link>
    </main>
  );
}

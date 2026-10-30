"use client";

import { useEffect } from "react";
import Link from "next/link";
import { RefreshCw } from "lucide-react";
import { BrandMark } from "@/components/layout/BrandMark";
import { Button, buttonStyles } from "@/components/ui/Button";
import { useT } from "@/providers/LocaleProvider";

/**
 * Shown when a page throws while rendering. It sits inside the root layout,
 * so the language provider is available. (In this Next.js version the
 * recovery callback is `retry`, not the older `reset`.)
 */
export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const t = useT();

  useEffect(() => {
    // A real deployment would send this to an error-reporting service.
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 px-6 text-center">
      <BrandMark className="h-12 w-12" />
      <div>
        <h1 className="text-2xl font-bold text-ink-950">{t("common.error.title")}</h1>
        <p className="mx-auto mt-1.5 max-w-md text-sm text-ink-600">{t("common.error.body")}</p>
      </div>
      <div className="flex flex-wrap justify-center gap-3">
        <Button onClick={() => retry()}>
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          {t("common.actions.retry")}
        </Button>
        <Link href="/" className={buttonStyles({ variant: "outline" })}>
          {t("common.notFound.home")}
        </Link>
      </div>
    </main>
  );
}

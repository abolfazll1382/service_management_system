"use client";

import { useCallback, useEffect } from "react";
import Link from "next/link";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import { buttonStyles } from "@/components/ui/Button";
import { useAsync } from "@/hooks/useAsync";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { catalogApi } from "@/lib/api";
import { ApiError } from "@/types/api";
import { useLocale, useT } from "@/providers/LocaleProvider";
import { ApplyForm } from "./ApplyForm";
import { useApplyWizardStore } from "./applyWizardStore";

/** Loads the service, handles "missing / switched off", then hands over to the form. */
export function ApplyWizard({ serviceId }: { serviceId: string }) {
  const t = useT();
  const { locale } = useLocale();
  const errorMessage = useErrorMessage();
  const reset = useApplyWizardStore((state) => state.reset);

  // A fresh application always starts at step one, even after a previous one.
  useEffect(() => {
    reset();
    return reset;
  }, [serviceId, reset]);

  const load = useCallback(() => catalogApi.getService(serviceId), [serviceId]);
  const { data: service, error, isLoading, refetch } = useAsync(load);

  const back = (
    <Link href="/services" className={buttonStyles({ variant: "outline" })}>
      {t("catalog.detail.back")}
    </Link>
  );

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      {error && !service ? (
        error instanceof ApiError && error.code === "not_found" ? (
          <EmptyState title={t("catalog.detail.notFound")} action={back} />
        ) : (
          <ErrorState message={errorMessage(error)} onRetry={refetch} />
        )
      ) : isLoading && !service ? (
        <Skeleton className="h-96" />
      ) : service && !service.isActive ? (
        <div className="space-y-4">
          <h1 className="text-2xl font-extrabold text-ink-950">{service.title[locale]}</h1>
          <Alert tone="warning">{t("catalog.detail.unavailable")}</Alert>
          {back}
        </div>
      ) : service ? (
        <ApplyForm service={service} />
      ) : null}
    </div>
  );
}

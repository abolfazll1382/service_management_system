"use client";

import { useCallback } from "react";
import Link from "next/link";
import { CheckCircle2, Clock } from "lucide-react";
import { DepartmentBadge } from "@/components/domain/DepartmentBadge";
import { Alert } from "@/components/ui/Alert";
import { buttonStyles } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Spinner";
import { useAsync } from "@/hooks/useAsync";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useSession } from "@/hooks/useSession";
import { catalogApi } from "@/lib/api";
import { getDepartment } from "@/lib/catalog";
import { loginUrl } from "@/lib/auth/redirect";
import { ApiError } from "@/types/api";
import { useLocale, useT } from "@/providers/LocaleProvider";

export function ServiceDetailView({ serviceId }: { serviceId: string }) {
  const t = useT();
  const { locale } = useLocale();
  const { user, hydrated } = useSession();
  const errorMessage = useErrorMessage();

  const load = useCallback(() => catalogApi.getService(serviceId), [serviceId]);
  const { data: service, error, isLoading, refetch } = useAsync(load);

  const back = (
    <Link href="/services" className="text-sm font-medium text-tile-700 underline-offset-4 hover:underline">
      {t("catalog.detail.back")}
    </Link>
  );

  if (error && !service) {
    if (error instanceof ApiError && error.code === "not_found") {
      return (
        <div className="mx-auto max-w-3xl px-4 py-16">
          <EmptyState title={t("catalog.detail.notFound")} action={back} />
        </div>
      );
    }
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <ErrorState message={errorMessage(error)} onRetry={refetch} />
      </div>
    );
  }
  if (isLoading && !service) {
    return (
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Skeleton className="h-96" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (!service) return null;

  const applyPath = `/apply/${service.id}`;
  const department = getDepartment(service.departmentId);

  let action;
  if (!hydrated) {
    action = <Skeleton className="h-10 w-full" />;
  } else if (!service.isActive) {
    action = <Alert tone="warning">{t("catalog.detail.unavailable")}</Alert>;
  } else if (user === null) {
    action = (
      <div className="flex flex-col gap-2">
        <Link href={loginUrl("/register", applyPath)} className={buttonStyles({ fullWidth: true })}>
          {t("catalog.detail.registerToApply")}
        </Link>
        <Link href={loginUrl("/login", applyPath)} className={buttonStyles({ variant: "outline", fullWidth: true })}>
          {t("catalog.detail.signInToApply")}
        </Link>
      </div>
    );
  } else if (user.role === "customer") {
    action = (
      <Link href={applyPath} className={buttonStyles({ fullWidth: true, size: "lg" })}>
        {t("catalog.detail.apply")}
      </Link>
    );
  } else {
    action = <Alert tone="info">{t("catalog.detail.staffNotice")}</Alert>;
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="mb-6">{back}</div>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <article>
          <DepartmentBadge departmentId={service.departmentId} />
          <h1 className="mt-2 text-3xl font-extrabold text-ink-950">{service.title[locale]}</h1>
          <p className="mt-2 text-lg text-ink-600">{service.summary[locale]}</p>

          <h2 className="mt-8 text-lg font-bold text-ink-950">{t("catalog.detail.about")}</h2>
          <p className="mt-2 max-w-prose text-ink-700">{service.description[locale]}</p>

          <h2 className="mt-8 text-lg font-bold text-ink-950">{t("catalog.detail.prepare")}</h2>
          <ul className="mt-3 space-y-2.5">
            {service.requirements.map((requirement) => (
              <li key={requirement.en} className="flex items-start gap-2.5 text-ink-700">
                <CheckCircle2 className="mt-1 h-4.5 w-4.5 shrink-0 text-tile-600" aria-hidden="true" />
                {requirement[locale]}
              </li>
            ))}
          </ul>
        </article>

        <aside>
          <Card className="lg:sticky lg:top-24">
            <CardContent className="space-y-5">
              <dl className="space-y-4">
                <div>
                  <dt className="text-xs font-medium text-ink-500">{t("catalog.detail.department")}</dt>
                  <dd className="mt-0.5 font-semibold text-ink-900">{department.name[locale]}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-ink-500">{t("catalog.detail.processing")}</dt>
                  <dd className="mt-0.5 flex items-center gap-1.5 font-semibold text-ink-900">
                    <Clock className="h-4 w-4 text-ink-500" aria-hidden="true" />
                    {t("catalog.detail.days", { days: service.etaDays })}
                  </dd>
                </div>
              </dl>
              {action}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

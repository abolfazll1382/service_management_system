"use client";

import { useCallback, useState } from "react";
import { DepartmentIcon } from "@/components/domain/DepartmentBadge";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Spinner";
import { Switch } from "@/components/ui/Switch";
import { useAsync } from "@/hooks/useAsync";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { catalogApi } from "@/lib/api";
import { DEPARTMENTS } from "@/lib/catalog";
import type { ServiceListing } from "@/types/service";
import { useLocale, useT } from "@/providers/LocaleProvider";
import { useToast } from "@/providers/ToastProvider";

/** Admin-only: pause or resume each service. A paused service stays visible but refuses new requests. */
export function ServiceAvailabilityView() {
  const t = useT();
  const { locale } = useLocale();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [pendingId, setPendingId] = useState<string | null>(null);

  const load = useCallback(() => catalogApi.listServices(), []);
  const { data, error, isLoading, refetch, mutate } = useAsync(load);

  const setActive = async (service: ServiceListing, isActive: boolean) => {
    setPendingId(service.id);
    try {
      const updated = await catalogApi.setServiceActive(service.id, isActive);
      mutate((current) => (current ? current.map((item) => (item.id === updated.id ? updated : item)) : current));
      toast.success(t("staff.services.toasts.updated"));
    } catch (failure) {
      toast.error(errorMessage(failure));
    } finally {
      setPendingId(null);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title={t("staff.services.title")} subtitle={t("staff.services.subtitle")} />

      {error && !data ? (
        <ErrorState message={`${t("staff.services.error")} ${errorMessage(error)}`} onRetry={refetch} />
      ) : isLoading && !data ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} className="h-32" />
          ))}
        </div>
      ) : (
        <div className="space-y-5">
          {DEPARTMENTS.map((department) => {
            const services = (data ?? []).filter((service) => service.departmentId === department.id);
            if (services.length === 0) return null;
            return (
              <Card key={department.id}>
                <CardHeader className="flex items-center gap-2">
                  <DepartmentIcon departmentId={department.id} className="text-ink-500" />
                  <CardTitle>{department.name[locale]}</CardTitle>
                </CardHeader>
                <ul className="divide-y divide-ink-100">
                  {services.map((service) => (
                    <li key={service.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
                      <div className="min-w-0">
                        <p className="font-medium text-ink-950">{service.title[locale]}</p>
                        <p className={service.isActive ? "text-sm text-tile-700" : "text-sm text-saffron-700"}>
                          {service.isActive ? t("staff.services.on") : t("staff.services.off")}
                        </p>
                      </div>
                      <Switch
                        checked={service.isActive}
                        disabled={pendingId === service.id}
                        onChange={(next) => void setActive(service, next)}
                        label={t("staff.services.switchLabel", { service: service.title[locale] })}
                      />
                    </li>
                  ))}
                </ul>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

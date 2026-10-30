"use client";

import { useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ErrorState } from "@/components/ui/ErrorState";
import { FilterTabs } from "@/components/ui/FilterTabs";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAsync } from "@/hooks/useAsync";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { catalogApi } from "@/lib/api";
import { DEPARTMENTS } from "@/lib/catalog";
import { DEPARTMENT_IDS, type DepartmentId } from "@/types/department";
import { useLocale, useT } from "@/providers/LocaleProvider";
import { ServiceCard } from "./ServiceCard";

type Filter = DepartmentId | "all";

export function ServicesView() {
  const t = useT();
  const { locale } = useLocale();
  const router = useRouter();
  const params = useSearchParams();
  const errorMessage = useErrorMessage();

  const requested = params.get("department");
  const department: Filter = DEPARTMENT_IDS.find((id) => id === requested) ?? "all";

  const load = useCallback(() => catalogApi.listServices(), []);
  const { data, error, isLoading, refetch } = useAsync(load);

  const options = [
    { value: "all" as Filter, label: t("catalog.list.allDepartments") },
    ...DEPARTMENTS.map((entry) => ({ value: entry.id as Filter, label: entry.name[locale] })),
  ];
  const visible = (data ?? []).filter((service) => department === "all" || service.departmentId === department);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <PageHeader title={t("catalog.list.title")} subtitle={t("catalog.hero.subtitle")} />
      <FilterTabs
        label={t("catalog.list.allDepartments")}
        options={options}
        value={department}
        onChange={(value) => router.replace(value === "all" ? "/services" : `/services?department=${value}`, { scroll: false })}
      />

      <div className="mt-6">
        {error && !data ? (
          <ErrorState message={errorMessage(error)} onRetry={refetch} />
        ) : isLoading && !data ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }, (_, index) => (
              <Skeleton key={index} className="h-44" />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <EmptyState title={t("common.state.noMatches")} />
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((service) => (
              <li key={service.id}>
                <ServiceCard service={service} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

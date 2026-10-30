"use client";

import { useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FilePlus2, FileText } from "lucide-react";
import { DepartmentBadge } from "@/components/domain/DepartmentBadge";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { Button, buttonStyles } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/Table";
import { useAsync } from "@/hooks/useAsync";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { requestsApi } from "@/lib/api";
import { findService } from "@/lib/catalog";
import { useFormat, useLocale, useT } from "@/providers/LocaleProvider";
import type { ServiceRequest } from "@/types/request";
import { CustomerRequestModal } from "./CustomerRequestModal";

export function MyRequestsView() {
  const t = useT();
  const { locale } = useLocale();
  const format = useFormat();
  const router = useRouter();
  const openId = useSearchParams().get("open");
  const errorMessage = useErrorMessage();

  const load = useCallback(() => requestsApi.listMine(), []);
  const { data, error, isLoading, refetch, mutate } = useAsync(load);

  const selected = data?.find((request) => request.id === openId) ?? null;
  const open = (request: ServiceRequest) => router.replace(`/my/requests?open=${request.id}`, { scroll: false });
  const close = () => router.replace("/my/requests", { scroll: false });
  const replaceInList = (updated: ServiceRequest) =>
    mutate((current) => (current ? current.map((request) => (request.id === updated.id ? updated : request)) : current));

  const titleOf = (request: ServiceRequest) => findService(request.serviceId)?.title[locale] ?? request.serviceId;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <PageHeader
        title={t("request.mine.title")}
        subtitle={t("request.mine.subtitle")}
        actions={
          <Link href="/services" className={buttonStyles()}>
            <FilePlus2 className="h-4 w-4" aria-hidden="true" />
            {t("request.mine.new")}
          </Link>
        }
      />

      {error && !data ? (
        <ErrorState message={`${t("request.mine.error")} ${errorMessage(error)}`} onRetry={refetch} />
      ) : isLoading && !data ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} className="h-16" />
          ))}
        </div>
      ) : data && data.length === 0 ? (
        <Card>
          <EmptyState
            icon={FileText}
            title={t("request.mine.empty.title")}
            body={t("request.mine.empty.body")}
            action={
              <Link href="/services" className={buttonStyles()}>
                {t("request.mine.browse")}
              </Link>
            }
          />
        </Card>
      ) : (
        <>
          {/* A table where there is room for one, stacked cards on a phone. */}
          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>{t("request.mine.columns.tracking")}</TableHead>
                  <TableHead>{t("request.mine.columns.service")}</TableHead>
                  <TableHead>{t("request.mine.columns.department")}</TableHead>
                  <TableHead>{t("request.mine.columns.status")}</TableHead>
                  <TableHead>{t("request.mine.columns.submitted")}</TableHead>
                  <TableHead>
                    <span className="sr-only">{t("common.actionsColumn")}</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data ?? []).map((request) => (
                  <TableRow key={request.id}>
                    <TableCell className="font-semibold text-ink-950">
                      <Ltr>{format.digits(request.trackingCode)}</Ltr>
                    </TableCell>
                    <TableCell className="font-medium text-ink-900">{titleOf(request)}</TableCell>
                    <TableCell>
                      <DepartmentBadge departmentId={request.departmentId} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={request.status} />
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{format.date(request.submittedAt)}</TableCell>
                    <TableCell className="text-end">
                      <Button variant="outline" size="sm" onClick={() => open(request)}>
                        {t("common.actions.view")}
                        <span className="sr-only"> {titleOf(request)}</span>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <ul className="space-y-3 md:hidden">
            {(data ?? []).map((request) => (
              <li key={request.id}>
                <button
                  type="button"
                  onClick={() => open(request)}
                  className="w-full rounded-xl border border-ink-200 bg-white p-4 text-start focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tile-600"
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-semibold text-ink-950">{titleOf(request)}</span>
                    <StatusBadge status={request.status} />
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-600">
                    <Ltr>{format.digits(request.trackingCode)}</Ltr>
                    <DepartmentBadge departmentId={request.departmentId} />
                    <span>{format.date(request.submittedAt)}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <CustomerRequestModal request={selected} onClose={close} onChanged={replaceInList} />
    </div>
  );
}

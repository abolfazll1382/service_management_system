"use client";

import { useCallback, useState } from "react";
import { ScrollText } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Skeleton } from "@/components/ui/Spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/Table";
import { useAsync } from "@/hooks/useAsync";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { auditApi } from "@/lib/api";
import { findService } from "@/lib/catalog";
import type { AuditEntry } from "@/types/audit";
import { useFormat, useLocale, useT } from "@/providers/LocaleProvider";

const PAGE_SIZE = 15;

/** Read-only trail of sign-ins and changes. Entries hold identifiers, never message text or full IDs. */
export function AuditView() {
  const t = useT();
  const { locale } = useLocale();
  const format = useFormat();
  const errorMessage = useErrorMessage();
  const [page, setPage] = useState(1);

  const load = useCallback(() => auditApi.list({ page, pageSize: PAGE_SIZE }), [page]);
  const { data, error, isLoading, refetch } = useAsync(load);

  const actorOf = (entry: AuditEntry) =>
    entry.actor ? (
      <>
        <span className="font-medium text-ink-900">{entry.actor.name[locale]}</span>
        <span className="block text-xs text-ink-500">{t(`common.role.${entry.actor.role}`)}</span>
      </>
    ) : (
      <span className="text-ink-400">{t("staff.audit.system")}</span>
    );

  // A target is an identifier (username, masked ID, tracking code, service id), stored without any wording
  // so it reads the same in every language. Service events show the service's name; a purely numeric
  // target — a tracking code — gets localized digits; anything else is shown as stored.
  const targetOf = (entry: AuditEntry) => {
    const { target, action } = entry;
    if (!target) return <span className="text-ink-400">—</span>;
    if (action === "service_paused" || action === "service_resumed") return <>{findService(target)?.title[locale] ?? target}</>;
    return <Ltr>{/^\d+$/.test(target) ? format.digits(target) : target}</Ltr>;
  };

  const items = data?.items ?? [];

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title={t("staff.audit.title")} subtitle={t("staff.audit.subtitle")} />

      {error && !data ? (
        <ErrorState message={`${t("staff.audit.error")} ${errorMessage(error)}`} onRetry={refetch} />
      ) : isLoading && !data ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }, (_, index) => (
            <Skeleton key={index} className="h-12" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState icon={ScrollText} title={t("staff.audit.empty")} />
        </Card>
      ) : (
        <>
          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>{t("staff.audit.columns.time")}</TableHead>
                  <TableHead>{t("staff.audit.columns.actor")}</TableHead>
                  <TableHead>{t("staff.audit.columns.action")}</TableHead>
                  <TableHead>{t("staff.audit.columns.target")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="whitespace-nowrap">{format.dateTime(entry.at)}</TableCell>
                    <TableCell>{actorOf(entry)}</TableCell>
                    <TableCell className="font-medium text-ink-900">{t(`staff.audit.actions.${entry.action}`)}</TableCell>
                    <TableCell>{targetOf(entry)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <ul className="space-y-3 md:hidden">
            {items.map((entry) => (
              <li key={entry.id} className="rounded-xl border border-ink-200 bg-white p-4">
                <p className="font-semibold text-ink-950">{t(`staff.audit.actions.${entry.action}`)}</p>
                <p className="text-xs text-ink-500">{format.dateTime(entry.at)}</p>
                <div className="mt-2 flex flex-wrap items-start justify-between gap-3 text-sm text-ink-700">
                  <div>{actorOf(entry)}</div>
                  <div>{targetOf(entry)}</div>
                </div>
              </li>
            ))}
          </ul>

          <Pagination page={data?.page ?? 1} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}

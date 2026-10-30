"use client";

import { useCallback, useState } from "react";
import { Pencil, UserPlus } from "lucide-react";
import { DepartmentBadge } from "@/components/domain/DepartmentBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/Table";
import { useAsync } from "@/hooks/useAsync";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useSession } from "@/hooks/useSession";
import { staffApi } from "@/lib/api";
import type { StaffAccount } from "@/types/user";
import { useFormat, useLocale, useT } from "@/providers/LocaleProvider";
import { StaffFormModal, type StaffFormTarget } from "./StaffFormModal";

export function TeamView() {
  const t = useT();
  const { locale } = useLocale();
  const format = useFormat();
  const errorMessage = useErrorMessage();
  const { user } = useSession();
  const [target, setTarget] = useState<StaffFormTarget | null>(null);

  const load = useCallback(() => staffApi.list(), []);
  const { data, error, isLoading, refetch } = useAsync(load);

  const departmentsOf = (member: StaffAccount) =>
    member.role === "admin" ? (
      <Badge tone="info">{t("staff.topbar.allDepartments")}</Badge>
    ) : (
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {member.departmentIds.map((id) => (
          <DepartmentBadge key={id} departmentId={id} />
        ))}
      </div>
    );

  const statusOf = (member: StaffAccount) => (
    <Badge tone={member.isActive ? "success" : "closed"}>{member.isActive ? t("common.state.active") : t("common.state.inactive")}</Badge>
  );

  const actionOf = (member: StaffAccount) =>
    member.role === "staff" ? (
      <Button variant="outline" size="sm" onClick={() => setTarget({ mode: "edit", member })}>
        <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
        {t("staff.team.edit")}
        <span className="sr-only"> {member.name[locale]}</span>
      </Button>
    ) : (
      <span className="text-xs text-ink-400">{t("staff.team.notEditable")}</span>
    );

  const nameOf = (member: StaffAccount) => (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span className="font-semibold text-ink-950">{member.name[locale]}</span>
      {member.id === user?.id && <Badge tone="neutral">{t("staff.team.you")}</Badge>}
    </span>
  );

  const members = data ?? [];

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title={t("staff.team.title")}
        subtitle={t("staff.team.subtitle")}
        actions={
          <Button onClick={() => setTarget({ mode: "create" })}>
            <UserPlus className="h-4 w-4" aria-hidden="true" />
            {t("staff.team.add")}
          </Button>
        }
      />

      {error && !data ? (
        <ErrorState message={`${t("staff.team.error")} ${errorMessage(error)}`} onRetry={refetch} />
      ) : isLoading && !data ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-14" />
          ))}
        </div>
      ) : (
        <>
          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>{t("staff.team.columns.name")}</TableHead>
                  <TableHead>{t("staff.team.columns.username")}</TableHead>
                  <TableHead>{t("staff.team.columns.departments")}</TableHead>
                  <TableHead>{t("staff.team.columns.status")}</TableHead>
                  <TableHead>{t("staff.team.columns.created")}</TableHead>
                  <TableHead>
                    <span className="sr-only">{t("common.actionsColumn")}</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell>{nameOf(member)}</TableCell>
                    <TableCell>
                      <Ltr>{member.username}</Ltr>
                    </TableCell>
                    <TableCell>{departmentsOf(member)}</TableCell>
                    <TableCell>{statusOf(member)}</TableCell>
                    <TableCell className="whitespace-nowrap">{format.date(member.createdAt)}</TableCell>
                    <TableCell className="text-end">{actionOf(member)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <ul className="space-y-3 md:hidden">
            {members.map((member) => (
              <li key={member.id} className="rounded-xl border border-ink-200 bg-white p-4">
                <div className="flex items-start justify-between gap-3">
                  {nameOf(member)}
                  {statusOf(member)}
                </div>
                <p className="mt-0.5 text-sm text-ink-600">
                  <Ltr>{member.username}</Ltr>
                </p>
                <div className="mt-2">{departmentsOf(member)}</div>
                <div className="mt-3">{actionOf(member)}</div>
              </li>
            ))}
          </ul>
        </>
      )}

      <StaffFormModal target={target} onClose={() => setTarget(null)} onSaved={refetch} />
    </div>
  );
}

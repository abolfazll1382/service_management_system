"use client";

import { useCallback, useState } from "react";
import { Inbox, Search } from "lucide-react";
import { DepartmentBadge } from "@/components/domain/DepartmentBadge";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { FilterTabs, type FilterOption } from "@/components/ui/FilterTabs";
import { Input } from "@/components/ui/Input";
import { Ltr } from "@/components/ui/Ltr";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Spinner";
import { Stat } from "@/components/ui/Stat";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/Table";
import { useAsync } from "@/hooks/useAsync";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useSession } from "@/hooks/useSession";
import { requestsApi } from "@/lib/api";
import { visibleDepartments } from "@/lib/auth/policies";
import { findService, getDepartment } from "@/lib/catalog";
import { DEPARTMENT_IDS, type DepartmentId } from "@/types/department";
import { REQUEST_STATUSES, type RequestStatus, type ServiceRequest } from "@/types/request";
import { useFormat, useLocale, useT } from "@/providers/LocaleProvider";
import { RequestWorkPanel } from "./RequestWorkPanel";

const PAGE_SIZE = 10;

type StatusFilter = RequestStatus | "all";
type DepartmentFilter = DepartmentId | "all";

/**
 * The work queue. The server already limits it to the caller's departments;
 * the department filter only offers what the account can see, and an
 * administrator (who can see everything) gets all of them.
 */
export function QueueView() {
  const t = useT();
  const { locale } = useLocale();
  const format = useFormat();
  const errorMessage = useErrorMessage();
  const { user } = useSession();

  const [status, setStatus] = useState<StatusFilter>("all");
  const [department, setDepartment] = useState<DepartmentFilter>("all");
  const [mineOnly, setMineOnly] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<ServiceRequest | null>(null);
  const search = useDebouncedValue(searchInput.trim(), 300);

  const load = useCallback(
    () =>
      requestsApi.queue({
        status: status === "all" ? undefined : status,
        departmentId: department === "all" ? undefined : department,
        assignment: mineOnly ? "mine" : undefined,
        search: search === "" ? undefined : search,
        page,
        pageSize: PAGE_SIZE,
      }),
    [status, department, mineOnly, search, page],
  );
  const { data, error, isLoading, refetch, mutate } = useAsync(load);

  if (!user) return null; // RequireAuth guarantees a user; this narrows the type

  const departments = visibleDepartments(user);
  const showDepartment = departments.length > 1;
  const filtersActive = status !== "all" || department !== "all" || mineOnly || search !== "";

  /** Any change to the filters starts again from the first page. */
  const narrow = <Value,>(setter: (value: Value) => void) => (value: Value) => {
    setter(value);
    setPage(1);
  };
  const clearFilters = () => {
    setStatus("all");
    setDepartment("all");
    setMineOnly(false);
    setSearchInput("");
    setPage(1);
  };

  const handleChanged = (updated: ServiceRequest) => {
    setOpen(updated);
    mutate((current) =>
      current ? { ...current, items: current.items.map((item) => (item.id === updated.id ? updated : item)) } : current,
    );
    refetch(); // the counts, and whether the request still belongs in this filter, may have changed
  };

  const counts = data?.counts;
  const totalInScope = counts ? REQUEST_STATUSES.reduce((sum, key) => sum + counts[key], 0) : 0;
  const tabs: FilterOption<StatusFilter>[] = [
    { value: "all", label: t("common.state.all"), count: counts ? totalInScope : undefined },
    ...REQUEST_STATUSES.map((value) => ({ value, label: t(`common.status.${value}`), count: counts?.[value] })),
  ];

  const titleOf = (request: ServiceRequest) => findService(request.serviceId)?.title[locale] ?? request.serviceId;
  const assigneeOf = (request: ServiceRequest) =>
    request.assignee ? request.assignee.name[locale] : <span className="text-ink-400">{t("staff.queue.unassigned")}</span>;
  const items = data?.items ?? [];

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title={t("staff.overview.title")}
        subtitle={user.role === "admin" ? t("staff.overview.subtitleAdmin") : t("staff.overview.subtitleStaff")}
      />

      <dl className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t("staff.overview.stats.total")} value={counts ? format.number(totalInScope) : "–"} />
        <Stat
          label={t("staff.overview.stats.awaiting")}
          value={counts ? format.number(counts.pending_review) : "–"}
          emphasis={(counts?.pending_review ?? 0) > 0}
        />
        <Stat label={t("staff.overview.stats.inProgress")} value={counts ? format.number(counts.in_progress) : "–"} />
        <Stat label={t("staff.overview.stats.correction")} value={counts ? format.number(counts.needs_correction) : "–"} />
      </dl>

      <div className="mb-4 space-y-3">
        <FilterTabs
          label={t("staff.queue.filterStatus")}
          options={tabs}
          value={status}
          onChange={narrow(setStatus)}
          formatCount={format.number}
        />
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-56 flex-1 sm:max-w-sm">
            <Search
              className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
              aria-hidden="true"
            />
            <Input
              type="search"
              aria-label={t("staff.queue.searchLabel")}
              placeholder={t("staff.queue.search")}
              value={searchInput}
              onChange={(event) => {
                setSearchInput(event.target.value);
                setPage(1);
              }}
              className="ps-9"
            />
          </div>
          {showDepartment && (
            <div className="w-full sm:w-52">
              <Select
                aria-label={t("staff.queue.filterDepartment")}
                value={department}
                onChange={(event) => narrow(setDepartment)(event.target.value as DepartmentFilter)}
              >
                <option value="all">{t("staff.topbar.allDepartments")}</option>
                {DEPARTMENT_IDS.filter((id) => departments.includes(id)).map((id) => (
                  <option key={id} value={id}>
                    {getDepartment(id).name[locale]}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={mineOnly}
              onChange={(event) => narrow(setMineOnly)(event.target.checked)}
              className="h-4 w-4 rounded border-ink-300 accent-tile-700"
            />
            {t("staff.queue.assignedToMe")}
          </label>
        </div>
      </div>

      {error && !data ? (
        <ErrorState message={`${t("staff.queue.error")} ${errorMessage(error)}`} onRetry={refetch} />
      ) : isLoading && !data ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-14" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            icon={Inbox}
            title={filtersActive ? t("common.state.noMatches") : t("staff.queue.empty")}
            action={
              filtersActive ? (
                <Button variant="outline" onClick={clearFilters}>
                  {t("staff.queue.clearFilters")}
                </Button>
              ) : undefined
            }
          />
        </Card>
      ) : (
        <>
          <p className="mb-2 text-sm text-ink-500" aria-live="polite">
            {t("staff.queue.resultCount", { count: data?.total ?? 0 })}
          </p>

          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>{t("staff.queue.columns.tracking")}</TableHead>
                  <TableHead>{t("staff.queue.columns.customer")}</TableHead>
                  <TableHead>{t("staff.queue.columns.service")}</TableHead>
                  {showDepartment && <TableHead>{t("staff.queue.columns.department")}</TableHead>}
                  <TableHead>{t("staff.queue.columns.status")}</TableHead>
                  <TableHead>{t("staff.queue.columns.assignee")}</TableHead>
                  <TableHead>{t("staff.queue.columns.submitted")}</TableHead>
                  <TableHead>
                    <span className="sr-only">{t("common.actionsColumn")}</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((request) => (
                  <TableRow key={request.id}>
                    <TableCell className="font-semibold text-ink-950">
                      <Ltr>{format.digits(request.trackingCode)}</Ltr>
                    </TableCell>
                    <TableCell className="font-medium text-ink-900">{request.customer.fullName}</TableCell>
                    <TableCell>{titleOf(request)}</TableCell>
                    {showDepartment && (
                      <TableCell>
                        <DepartmentBadge departmentId={request.departmentId} />
                      </TableCell>
                    )}
                    <TableCell>
                      <StatusBadge status={request.status} />
                    </TableCell>
                    <TableCell>{assigneeOf(request)}</TableCell>
                    <TableCell className="whitespace-nowrap">{format.date(request.submittedAt)}</TableCell>
                    <TableCell className="text-end">
                      <Button variant="outline" size="sm" onClick={() => setOpen(request)}>
                        {t("common.actions.open")}
                        <span className="sr-only">
                          {" "}
                          {request.customer.fullName} — {titleOf(request)}
                        </span>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <ul className="space-y-3 md:hidden">
            {items.map((request) => (
              <li key={request.id}>
                <button
                  type="button"
                  onClick={() => setOpen(request)}
                  className="w-full rounded-xl border border-ink-200 bg-white p-4 text-start focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tile-600"
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-semibold text-ink-950">{request.customer.fullName}</span>
                    <StatusBadge status={request.status} />
                  </div>
                  <p className="mt-0.5 text-sm text-ink-700">{titleOf(request)}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-600">
                    <Ltr>{format.digits(request.trackingCode)}</Ltr>
                    {showDepartment && <DepartmentBadge departmentId={request.departmentId} />}
                    <span>{assigneeOf(request)}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>

          <Pagination page={data?.page ?? 1} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPageChange={setPage} />
        </>
      )}

      <RequestWorkPanel request={open} onClose={() => setOpen(null)} onChanged={handleChanged} />
    </div>
  );
}

"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useT } from "@/providers/LocaleProvider";
import { Button } from "./Button";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const t = useT();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;

  return (
    <nav className="flex items-center justify-between gap-3 pt-4" aria-label={t("common.pagination.summary", { page, total: pages })}>
      <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        {/* Chevrons mirror with the reading direction: "previous" points to the start. */}
        <ChevronLeft className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
        {t("common.pagination.previous")}
      </Button>
      <span className="text-sm text-ink-600" aria-live="polite">
        {t("common.pagination.summary", { page, total: pages })}
      </span>
      <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
        {t("common.pagination.next")}
        <ChevronRight className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
      </Button>
    </nav>
  );
}

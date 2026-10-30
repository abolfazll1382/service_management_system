"use client";

import { Banknote, Boxes, Car, Home, type LucideIcon } from "lucide-react";
import { getDepartment } from "@/lib/catalog";
import { cn } from "@/lib/utils/cn";
import { useLocale } from "@/providers/LocaleProvider";
import type { DepartmentIconKey, DepartmentId } from "@/types/department";

const ICONS: Record<DepartmentIconKey, LucideIcon> = {
  banknote: Banknote,
  boxes: Boxes,
  car: Car,
  home: Home,
};

export function DepartmentIcon({ departmentId, className }: { departmentId: DepartmentId; className?: string }) {
  const Icon = ICONS[getDepartment(departmentId).icon];
  return <Icon className={cn("h-4 w-4", className)} aria-hidden="true" />;
}

/** Icon + department name in the active language. */
export function DepartmentBadge({ departmentId, className }: { departmentId: DepartmentId; className?: string }) {
  const { locale } = useLocale();
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-sm text-ink-700", className)}>
      <DepartmentIcon departmentId={departmentId} className="text-ink-500" />
      {getDepartment(departmentId).name[locale]}
    </span>
  );
}

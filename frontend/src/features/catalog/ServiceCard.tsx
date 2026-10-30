"use client";

import Link from "next/link";
import { Clock } from "lucide-react";
import { DepartmentBadge } from "@/components/domain/DepartmentBadge";
import { Badge } from "@/components/ui/Badge";
import { useLocale, useT } from "@/providers/LocaleProvider";
import type { ServiceListing } from "@/types/service";

export function ServiceCard({ service }: { service: ServiceListing }) {
  const t = useT();
  const { locale } = useLocale();
  return (
    <Link
      href={`/services/${service.id}`}
      className="group flex h-full flex-col rounded-xl border border-ink-200 bg-white p-5 transition-colors hover:border-tile-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tile-600"
    >
      <div className="flex items-start justify-between gap-3">
        <DepartmentBadge departmentId={service.departmentId} />
        {!service.isActive && <Badge tone="attention">{t("catalog.list.unavailable")}</Badge>}
      </div>
      <h3 className="mt-3 text-lg font-bold text-ink-950 group-hover:text-tile-800">{service.title[locale]}</h3>
      <p className="mt-1 flex-1 text-sm text-ink-600">{service.summary[locale]}</p>
      <p className="mt-4 flex items-center gap-1.5 text-sm text-ink-500">
        <Clock className="h-4 w-4" aria-hidden="true" />
        {t("catalog.list.eta", { days: service.etaDays })}
      </p>
    </Link>
  );
}

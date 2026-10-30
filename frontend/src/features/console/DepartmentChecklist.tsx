"use client";

import { useId } from "react";
import { DepartmentIcon } from "@/components/domain/DepartmentBadge";
import { DEPARTMENTS } from "@/lib/catalog";
import { cn } from "@/lib/utils/cn";
import type { DepartmentId } from "@/types/department";
import { useLocale } from "@/providers/LocaleProvider";

interface DepartmentChecklistProps {
  legend: string;
  value: readonly DepartmentId[];
  onChange: (next: DepartmentId[]) => void;
  error?: string;
}

/** Which departments an account may work in. Controlled, so it plugs into react-hook-form's `Controller`. */
export function DepartmentChecklist({ legend, value, onChange, error }: DepartmentChecklistProps) {
  const { locale } = useLocale();
  const errorId = useId();

  const toggle = (id: DepartmentId, checked: boolean) =>
    // Rebuilt in catalog order so the stored list doesn't depend on click order.
    onChange(DEPARTMENTS.map((department) => department.id).filter((candidate) => (candidate === id ? checked : value.includes(candidate))));

  return (
    <fieldset aria-describedby={error ? errorId : undefined}>
      <legend className="mb-1.5 text-sm font-medium text-ink-800">{legend}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {DEPARTMENTS.map(({ id, name }) => {
          const checked = value.includes(id);
          return (
            <label
              key={id}
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition-colors",
                checked ? "border-tile-600 bg-tile-50 text-ink-950" : "border-ink-200 bg-white text-ink-700 hover:border-ink-300",
              )}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={(event) => toggle(id, event.target.checked)}
                className="h-4 w-4 shrink-0 accent-tile-700"
              />
              <DepartmentIcon departmentId={id} className="shrink-0 text-ink-500" />
              {name[locale]}
            </label>
          );
        })}
      </div>
      {error && (
        <p id={errorId} role="alert" className="mt-1.5 text-sm text-rose-700">
          {error}
        </p>
      )}
    </fieldset>
  );
}

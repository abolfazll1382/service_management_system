"use client";

import { Ltr } from "@/components/ui/Ltr";
import { useFormat, useLocale } from "@/providers/LocaleProvider";
import type { Service, ServiceDetails } from "@/types/service";

/**
 * Shows the answers a customer gave to a service's own questions, labelled in
 * the active language. Driven by the service definition, so a new service
 * needs no new display code.
 */
export function DetailList({ service, details }: { service: Service; details: ServiceDetails }) {
  const { locale } = useLocale();
  const format = useFormat();

  const rows = service.fields.flatMap((field) => {
    const raw = details[field.key];
    if (raw === undefined || raw === "") return [];
    let value: string;
    if (field.kind === "select") {
      value = field.options.find((option) => option.value === raw)?.label[locale] ?? String(raw);
    } else if (field.kind === "number" && typeof raw === "number") {
      value = field.unit ? `${format.number(raw)} ${field.unit[locale]}` : format.number(raw);
    } else {
      value = String(raw);
    }
    return [{ key: field.key, label: field.label[locale], value, isNumber: field.kind === "number" }];
  });

  if (rows.length === 0) return null;
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {rows.map((row) => (
        <div key={row.key}>
          <dt className="text-xs font-medium text-ink-500">{row.label}</dt>
          {/* plaintext: a typed value like "Packaging workshop." keeps its own punctuation order inside an RTL page,
              while the cell stays aligned with its label. */}
          <dd className="text-sm text-ink-900 [unicode-bidi:plaintext]">{row.isNumber ? <Ltr>{row.value}</Ltr> : row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

"use client";

import type { FieldErrors, UseFormRegister } from "react-hook-form";
import { SelectField, TextField } from "@/components/ui/FormField";
import { asNumber } from "@/lib/utils/forms";
import type { ApplyFormValues } from "@/lib/validation/request";
import { useLocale, useT } from "@/providers/LocaleProvider";
import type { FieldDef } from "@/types/service";

interface DynamicFieldProps {
  field: FieldDef;
  register: UseFormRegister<ApplyFormValues>;
  errors: FieldErrors<ApplyFormValues>;
}

/**
 * Renders ONE of a service's own questions from its definition. The wizard
 * has no per-service code: a new service is a new entry in lib/catalog, and
 * its form (and validation, and the staff view of the answers) follows.
 */
export function DynamicField({ field, register, errors }: DynamicFieldProps) {
  const t = useT();
  const { locale } = useLocale();
  const name = `details.${field.key}` as const;
  const id = `field-${field.key}`;
  const error = (errors.details as Record<string, { message?: string } | undefined> | undefined)?.[field.key]?.message;
  const label = field.kind === "number" && field.unit ? `${field.label[locale]} (${field.unit[locale]})` : field.label[locale];

  switch (field.kind) {
    case "text":
      return (
        <TextField
          id={id}
          label={label}
          required={field.required}
          optional={!field.required}
          maxLength={field.maxLength}
          dir="auto"
          error={error}
          {...register(name)}
        />
      );
    case "number":
      return (
        <TextField
          id={id}
          label={label}
          required={field.required}
          optional={!field.required}
          numeric
          hint={t("request.wizard.details.range", { min: field.min, max: field.max })}
          error={error}
          {...register(name, { setValueAs: asNumber })}
        />
      );
    case "select":
      return (
        <SelectField
          id={id}
          label={label}
          required={field.required}
          optional={!field.required}
          error={error}
          {...register(name, { setValueAs: (value: string) => (value === "" ? undefined : value) })}
        >
          <option value="">{t("common.state.choose")}</option>
          {field.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label[locale]}
            </option>
          ))}
        </SelectField>
      );
  }
}

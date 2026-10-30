import { z } from "zod";
import type { Translate } from "@/lib/i18n/types";
import type { FieldDef, Service, ServiceDetails } from "@/types/service";
import { REQUEST_STATUSES } from "@/types/request";
import { requiresNote } from "@/lib/domain/workflow";
import { acceptField } from "./fields";

const requiredIssue = (t: Translate, otherwise: Parameters<Translate>[0]) => ({
  error: (issue: { input?: unknown }) => (issue.input === undefined ? t("validation.required") : t(otherwise)),
});

/** Builds the validator for ONE field definition of a service. */
function fieldSchema(field: FieldDef, t: Translate): z.ZodType {
  switch (field.kind) {
    case "text": {
      const base = z
        .string(requiredIssue(t, "validation.required"))
        .trim()
        .max(field.maxLength, t("validation.text.max", { max: field.maxLength }));
      return field.required ? base.min(1, t("validation.required")) : base.optional();
    }
    case "number": {
      const base = z
        .number(requiredIssue(t, "validation.number.invalid"))
        .min(field.min, t("validation.number.min", { min: field.min }))
        .max(field.max, t("validation.number.max", { max: field.max }));
      return field.required ? base : base.optional();
    }
    case "select": {
      const values = field.options.map((option) => option.value);
      if (values.length === 0) throw new Error(`Select field "${field.key}" has no options`);
      const base = z.enum(values as [string, ...string[]], { error: () => t("validation.select") });
      return field.required ? base : base.optional();
    }
  }
}

/** Zod object for a service's extra fields; unknown keys are stripped. */
export function createDetailsSchema(fields: readonly FieldDef[], t: Translate) {
  const shape: Record<string, z.ZodType> = {};
  for (const field of fields) shape[field.key] = fieldSchema(field, t);
  return z.object(shape);
}

/** Narrows a parsed (statically unknown) object to the stored ServiceDetails shape. */
export function toServiceDetails(fields: readonly FieldDef[], parsed: Record<string, unknown>): ServiceDetails {
  const details: ServiceDetails = {};
  for (const field of fields) {
    const value = parsed[field.key];
    if (typeof value === "string" && value !== "") details[field.key] = value;
    if (typeof value === "number") details[field.key] = value;
  }
  return details;
}

export const descriptionField = (t: Translate) =>
  z
    .string({ error: () => t("validation.required") })
    .trim()
    .min(10, t("validation.description.min"))
    .max(1000, t("validation.description.max"));

/** Wizard form: notes + the service's own fields + consent. */
export function createApplyFormSchema(service: Service, t: Translate) {
  return z.object({
    description: descriptionField(t),
    details: createDetailsSchema(service.fields, t),
    confirm: acceptField(t),
  });
}

/** Statically the details are unknown — the runtime schema above is the guard. */
export interface ApplyFormValues {
  description: string;
  details: Record<string, string | number | undefined>;
  confirm: boolean;
}

export interface CreateRequestInput {
  serviceId: string;
  description: string;
  details: ServiceDetails;
}

export const createMessageSchema = (t: Translate) =>
  z.object({
    body: z
      .string({ error: () => t("validation.required") })
      .trim()
      .min(1, t("validation.required"))
      .max(1000, t("validation.description.max")),
    visibility: z.enum(["public", "internal"]),
  });
export type MessageInput = z.infer<ReturnType<typeof createMessageSchema>>;

export const statusSchema = z.enum(REQUEST_STATUSES);

/**
 * A status change with an optional note to the applicant. Rejecting a request
 * or asking for corrections REQUIRES the note (see requiresNote), so the rule
 * lives in the schema that both the work panel and the server run.
 */
export const createTransitionSchema = (t: Translate) =>
  z
    .object({
      to: statusSchema,
      note: z.string().trim().max(1000, t("validation.description.max")).optional(),
    })
    .refine((value) => !requiresNote(value.to) || (value.note ?? "") !== "", {
      path: ["note"],
      message: t("validation.note.required"),
    });
export type TransitionInput = z.infer<ReturnType<typeof createTransitionSchema>>;

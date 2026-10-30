import type { DepartmentId } from "./department";
import type { Localized } from "./i18n";

export interface SelectOption {
  value: string;
  label: Localized;
}

/**
 * A service describes its own extra form fields as data. The apply wizard
 * renders them and both the browser and the mock server build their Zod
 * schema from the same definition, so adding a service never means writing
 * a new form component or a second validator.
 */
export type FieldDef =
  | { kind: "text"; key: string; label: Localized; required: boolean; maxLength: number }
  | {
      kind: "number";
      key: string;
      label: Localized;
      required: boolean;
      min: number;
      max: number;
      unit?: Localized;
    }
  | {
      kind: "select";
      key: string;
      label: Localized;
      required: boolean;
      options: readonly SelectOption[];
    };

export interface Service {
  id: string;
  departmentId: DepartmentId;
  title: Localized;
  summary: Localized;
  description: Localized;
  /** What an applicant should have ready before starting. */
  requirements: readonly Localized[];
  /** Typical processing time, shown to set expectations. */
  etaDays: number;
  fields: readonly FieldDef[];
}

/** A service plus the admin-controlled availability flag. */
export interface ServiceListing extends Service {
  isActive: boolean;
}

/** Values entered for a service's extra fields, keyed by FieldDef.key. */
export type ServiceDetails = Record<string, string | number>;

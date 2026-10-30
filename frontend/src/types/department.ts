import type { Localized } from "./i18n";

/**
 * Departments are the unit of authorization: a staff member is granted a set
 * of departments, and every request belongs to exactly one. Adding a
 * department is a data change here plus an entry in lib/catalog — the
 * permission code (lib/auth/policies.ts) never mentions a specific one.
 */
export const DEPARTMENT_IDS = ["loan", "raw_material", "vehicle", "housing"] as const;
export type DepartmentId = (typeof DEPARTMENT_IDS)[number];

/** Icons are referenced by key so this data file stays free of React. */
export type DepartmentIconKey = "banknote" | "boxes" | "car" | "home";

export interface Department {
  id: DepartmentId;
  name: Localized;
  description: Localized;
  icon: DepartmentIconKey;
}

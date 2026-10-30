import type { Department, DepartmentId } from "@/types/department";

export const DEPARTMENTS: readonly Department[] = [
  {
    id: "loan",
    icon: "banknote",
    name: { fa: "تسهیلات و وام", en: "Loans & Financing" },
    description: { fa: "وام شخصی و تسهیلات کسب‌وکار", en: "Personal and business loan applications" },
  },
  {
    id: "raw_material",
    icon: "boxes",
    name: { fa: "مواد اولیه", en: "Raw Materials" },
    description: { fa: "تأمین مواد اولیه برای تولید", en: "Supply requests for production materials" },
  },
  {
    id: "vehicle",
    icon: "car",
    name: { fa: "خودرو", en: "Vehicles" },
    description: { fa: "خرید و خدمات خودرو", en: "Vehicle purchase and maintenance" },
  },
  {
    id: "housing",
    icon: "home",
    name: { fa: "مسکن", en: "Housing" },
    description: { fa: "واحد مسکونی و کمک‌هزینه اجاره", en: "Housing units and rent support" },
  },
];

const BY_ID = new Map<DepartmentId, Department>(DEPARTMENTS.map((department) => [department.id, department]));

/** Total over DepartmentId — tests/catalog.test.ts fails if one is missing. */
export function getDepartment(id: DepartmentId): Department {
  const department = BY_ID.get(id);
  if (!department) throw new Error(`Unknown department: ${id}`);
  return department;
}

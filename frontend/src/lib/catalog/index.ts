import type { DepartmentId } from "@/types/department";
import type { Service } from "@/types/service";
import { SERVICES } from "./services";

export { DEPARTMENTS, getDepartment } from "./departments";
export { SERVICES } from "./services";

const BY_ID = new Map<string, Service>(SERVICES.map((service) => [service.id, service]));

export function findService(id: string): Service | undefined {
  return BY_ID.get(id);
}

export function servicesInDepartment(departmentId: DepartmentId): readonly Service[] {
  return SERVICES.filter((service) => service.departmentId === departmentId);
}

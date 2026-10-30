import { describe, expect, it } from "vitest";
import { DEPARTMENTS, SERVICES, findService, getDepartment, servicesInDepartment } from "@/lib/catalog";
import { DEPARTMENT_IDS } from "@/types/department";
import { LOCALES } from "@/types/i18n";
import type { Localized } from "@/types/i18n";
import { createDetailsSchema } from "@/lib/validation/request";
import { identityTranslate } from "@/lib/validation/fields";

const bothLanguages = (value: Localized) => LOCALES.every((locale) => value[locale].trim().length > 0);

describe("departments", () => {
  it("has exactly one definition per department id, in both languages", () => {
    expect(DEPARTMENTS.map((department) => department.id).sort()).toEqual([...DEPARTMENT_IDS].sort());
    for (const department of DEPARTMENTS) {
      expect(bothLanguages(department.name), department.id).toBe(true);
      expect(bothLanguages(department.description), department.id).toBe(true);
      expect(getDepartment(department.id)).toBe(department);
    }
  });

  it("gives every department at least one service", () => {
    for (const id of DEPARTMENT_IDS) expect(servicesInDepartment(id).length, id).toBeGreaterThan(0);
  });
});

describe("services", () => {
  it("have unique ids and point at a real department", () => {
    const ids = SERVICES.map((service) => service.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const service of SERVICES) {
      expect(DEPARTMENT_IDS, service.id).toContain(service.departmentId);
      expect(findService(service.id)).toBe(service);
    }
  });

  it("are fully translated", () => {
    for (const service of SERVICES) {
      expect(bothLanguages(service.title), `${service.id} title`).toBe(true);
      expect(bothLanguages(service.summary), `${service.id} summary`).toBe(true);
      expect(bothLanguages(service.description), `${service.id} description`).toBe(true);
      expect(service.requirements.length, `${service.id} requirements`).toBeGreaterThan(0);
      for (const requirement of service.requirements) expect(bothLanguages(requirement), service.id).toBe(true);
      expect(service.etaDays).toBeGreaterThan(0);
    }
  });

  it("describe well-formed fields", () => {
    for (const service of SERVICES) {
      const keys = service.fields.map((field) => field.key);
      expect(new Set(keys).size, `${service.id} duplicate field keys`).toBe(keys.length);
      for (const field of service.fields) {
        expect(bothLanguages(field.label), `${service.id}.${field.key}`).toBe(true);
        if (field.kind === "number") {
          expect(field.min, `${service.id}.${field.key}`).toBeLessThan(field.max);
          if (field.unit) expect(bothLanguages(field.unit)).toBe(true);
        }
        if (field.kind === "select") {
          expect(field.options.length, `${service.id}.${field.key}`).toBeGreaterThan(0);
          const values = field.options.map((option) => option.value);
          expect(new Set(values).size, `${service.id}.${field.key} duplicate options`).toBe(values.length);
          for (const option of field.options) expect(bothLanguages(option.label)).toBe(true);
        }
      }
    }
  });

  it("build a validator without throwing, and reject an empty submission when something is required", () => {
    for (const service of SERVICES) {
      const schema = createDetailsSchema(service.fields, identityTranslate);
      const hasRequired = service.fields.some((field) => field.required);
      expect(schema.safeParse({}).success, service.id).toBe(!hasRequired);
    }
  });
});

import { z } from "zod";
import type { Translate } from "@/lib/i18n/types";
import { DEPARTMENT_IDS } from "@/types/department";
import { passwordField, usernameField } from "./fields";

const nameField = (t: Translate) =>
  z.string({ error: () => t("validation.names") }).trim().min(2, t("validation.names")).max(60, t("validation.names"));

const departmentsField = (t: Translate) =>
  z.array(z.enum(DEPARTMENT_IDS)).min(1, t("validation.departments"));

export const createStaffInputSchema = (t: Translate) =>
  z.object({
    nameFa: nameField(t),
    nameEn: nameField(t),
    username: usernameField(t),
    password: passwordField(t),
    departmentIds: departmentsField(t),
  });
export type CreateStaffInput = z.infer<ReturnType<typeof createStaffInputSchema>>;

export const updateStaffInputSchema = (t: Translate) =>
  z.object({
    departmentIds: departmentsField(t),
    isActive: z.boolean(),
  });
export type UpdateStaffInput = z.infer<ReturnType<typeof updateStaffInputSchema>>;

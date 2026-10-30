import { z } from "zod";
import type { Translate } from "@/lib/i18n/types";
import {
  acceptField,
  addressField,
  fullNameField,
  nationalIdField,
  passwordField,
  phoneField,
  postalCodeField,
} from "./fields";

/** What the (mock) server accepts. The form adds confirmation + consent on top. */
export const createRegisterInputSchema = (t: Translate) =>
  z.object({
    fullName: fullNameField(t),
    nationalId: nationalIdField(t),
    phone: phoneField(t),
    postalCode: postalCodeField(t),
    address: addressField(t),
    password: passwordField(t),
  });
export type RegisterInput = z.infer<ReturnType<typeof createRegisterInputSchema>>;

export const createRegisterSchema = (t: Translate) =>
  createRegisterInputSchema(t)
    .extend({
      confirmPassword: z.string(),
      acceptTerms: acceptField(t),
    })
    .refine((values) => values.password === values.confirmPassword, {
      path: ["confirmPassword"],
      message: t("validation.password.mismatch"),
    });
export type RegisterFormValues = z.infer<ReturnType<typeof createRegisterSchema>>;

/**
 * Login only checks shape, not the checksum: an invalid-looking ID should get
 * the same "incorrect credentials" answer as a wrong password rather than a
 * hint about which part was wrong.
 */
export const createCustomerLoginSchema = (t: Translate) =>
  z.object({
    nationalId: z.string({ error: () => t("validation.required") }).regex(/^\d{10}$/, t("validation.nationalId.format")),
    password: z.string({ error: () => t("validation.required") }).min(1, t("validation.required")),
  });
export type CustomerLoginInput = z.infer<ReturnType<typeof createCustomerLoginSchema>>;

export const createStaffLoginSchema = (t: Translate) =>
  z.object({
    username: z.string({ error: () => t("validation.required") }).trim().min(1, t("validation.required")),
    password: z.string({ error: () => t("validation.required") }).min(1, t("validation.required")),
  });
export type StaffLoginInput = z.infer<ReturnType<typeof createStaffLoginSchema>>;

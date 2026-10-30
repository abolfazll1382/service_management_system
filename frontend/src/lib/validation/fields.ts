import { z } from "zod";
import type { Translate } from "@/lib/i18n/types";
import { isValidNationalId } from "@/lib/utils/persianUtils";

/**
 * Field builders take the translator, so each schema is built for the active
 * language and its messages are already localized when react-hook-form shows
 * them. The mock server builds the same schemas with `identityTranslate` —
 * it only needs pass/fail, so the message text is irrelevant there.
 *
 * `error: (issue) => …` covers the "field is missing entirely" case (an
 * unregistered or cleared input arrives as `undefined`), which Zod would
 * otherwise report with its own English text.
 */
const required = (t: Translate) => ({ error: () => t("validation.required") });

export const fullNameField = (t: Translate) =>
  z.string(required(t)).trim().min(2, t("validation.fullName")).max(100, t("validation.fullName"));

export const nationalIdField = (t: Translate) =>
  z
    .string(required(t))
    .regex(/^\d{10}$/, t("validation.nationalId.format"))
    .refine(isValidNationalId, t("validation.nationalId.checksum"));

export const phoneField = (t: Translate) => z.string(required(t)).regex(/^09\d{9}$/, t("validation.phone"));

export const postalCodeField = (t: Translate) =>
  z.string(required(t)).regex(/^\d{10}$/, t("validation.postalCode"));

export const addressField = (t: Translate) =>
  z.string(required(t)).trim().min(5, t("validation.address")).max(200, t("validation.address"));

/** Min 8 with at least one letter and one digit — a floor, not a full policy. */
export const passwordField = (t: Translate) =>
  z
    .string(required(t))
    .min(8, t("validation.password.min"))
    .regex(/[A-Za-z]/, t("validation.password.mix"))
    .regex(/\d/, t("validation.password.mix"));

export const usernameField = (t: Translate) =>
  z.string(required(t)).regex(/^[a-z][a-z0-9_]{2,19}$/, t("validation.username"));

export const acceptField = (t: Translate) => z.boolean().refine((value) => value, t("validation.accept"));

/** For server-side validation, where only the verdict matters. */
export const identityTranslate: Translate = (key) => key;

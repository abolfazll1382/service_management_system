"use client";

import { useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Wand2 } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField, TextareaField } from "@/components/ui/FormField";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useRedirectWhenSignedIn } from "@/hooks/useRedirectWhenSignedIn";
import { useRevalidateOnLocaleChange } from "@/hooks/useRevalidateOnLocaleChange";
import { authApi } from "@/lib/api";
import { safeNextPath } from "@/lib/auth/redirect";
import { useSessionStore } from "@/lib/auth/sessionStore";
import { createSampleRegistration } from "@/lib/demo/accounts";
import { asDigits } from "@/lib/utils/forms";
import { createRegisterSchema, type RegisterFormValues } from "@/lib/validation/auth";
import { ApiError } from "@/types/api";
import { useLocale, useT } from "@/providers/LocaleProvider";
import { useToast } from "@/providers/ToastProvider";
import { AuthCard } from "./AuthCard";

const EMPTY: RegisterFormValues = {
  fullName: "",
  nationalId: "",
  phone: "",
  postalCode: "",
  address: "",
  password: "",
  confirmPassword: "",
  acceptTerms: false,
};

function Fieldset({ legend, children }: { legend: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-4">
      <legend className="mb-1 border-b border-ink-100 pb-1.5 text-sm font-bold text-ink-900">{legend}</legend>
      {children}
    </fieldset>
  );
}

export function RegisterForm() {
  const t = useT();
  const { locale } = useLocale();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const next = safeNextPath(useSearchParams().get("next"), "/services");
  const [formError, setFormError] = useState<string | null>(null);

  const schema = useMemo(() => createRegisterSchema(t), [t]);
  const form = useForm<RegisterFormValues>({ resolver: zodResolver(schema), defaultValues: EMPTY });
  const { register, handleSubmit, reset, setError, formState } = form;
  const { errors, isSubmitting } = formState;
  useRevalidateOnLocaleChange(form);
  useRedirectWhenSignedIn(["customer"], next);

  const onSubmit = handleSubmit(async ({ fullName, nationalId, phone, postalCode, address, password }) => {
    setFormError(null);
    try {
      const result = await authApi.register({ fullName, nationalId, phone, postalCode, address, password });
      useSessionStore.getState().signIn(result);
      toast.success(t("auth.register.success"));
    } catch (error) {
      // A taken ID or number belongs on the field that caused it, not in a banner.
      if (error instanceof ApiError && error.code === "national_id_taken") {
        setError("nationalId", { message: t("errors.national_id_taken") });
      } else if (error instanceof ApiError && error.code === "phone_taken") {
        setError("phone", { message: t("errors.phone_taken") });
      } else {
        setFormError(errorMessage(error));
      }
    }
  });

  const loginHref = next === "/services" ? "/login" : `/login?next=${encodeURIComponent(next)}`;

  return (
    <AuthCard
      wide
      title={t("auth.register.title")}
      subtitle={t("auth.register.subtitle")}
      footer={
        <>
          {t("auth.register.haveAccount")}{" "}
          <Link href={loginHref} className="font-semibold text-tile-700 underline-offset-4 hover:underline">
            {t("common.nav.signIn")}
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-7">
        <Alert tone="info">{t("auth.register.notice")}</Alert>
        {formError && <Alert tone="danger">{formError}</Alert>}

        <Fieldset legend={t("auth.register.identity")}>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              id="fullName"
              label={t("common.fields.fullName")}
              placeholder={t("auth.placeholders.fullName")}
              autoComplete="name"
              required
              error={errors.fullName?.message}
              {...register("fullName")}
            />
            <TextField
              id="nationalId"
              label={t("common.fields.nationalId")}
              placeholder={t("auth.placeholders.nationalId")}
              numeric
              maxLength={20}
              required
              error={errors.nationalId?.message}
              {...register("nationalId", { setValueAs: asDigits })}
            />
          </div>
        </Fieldset>

        <Fieldset legend={t("auth.register.contact")}>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              id="phone"
              type="tel"
              label={t("common.fields.phone")}
              placeholder={t("auth.placeholders.phone")}
              numeric
              maxLength={20}
              autoComplete="tel"
              required
              error={errors.phone?.message}
              {...register("phone", { setValueAs: asDigits })}
            />
            <TextField
              id="postalCode"
              label={t("common.fields.postalCode")}
              placeholder={t("auth.placeholders.postalCode")}
              numeric
              maxLength={20}
              autoComplete="postal-code"
              required
              error={errors.postalCode?.message}
              {...register("postalCode", { setValueAs: asDigits })}
            />
          </div>
          <TextareaField
            id="address"
            label={t("common.fields.address")}
            placeholder={t("auth.placeholders.address")}
            rows={2}
            autoComplete="street-address"
            required
            error={errors.address?.message}
            {...register("address")}
          />
        </Fieldset>

        <Fieldset legend={t("auth.register.security")}>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              id="password"
              type="password"
              label={t("common.fields.password")}
              placeholder={t("auth.placeholders.password")}
              autoComplete="new-password"
              required
              error={errors.password?.message}
              {...register("password")}
            />
            <TextField
              id="confirmPassword"
              type="password"
              label={t("common.fields.confirmPassword")}
              autoComplete="new-password"
              required
              error={errors.confirmPassword?.message}
              {...register("confirmPassword")}
            />
          </div>
          <div>
            <label className="flex items-start gap-2.5 text-sm text-ink-800">
              <input
                type="checkbox"
                className="mt-1.5 h-4 w-4 rounded border-ink-300 accent-tile-700"
                aria-invalid={errors.acceptTerms ? true : undefined}
                aria-describedby={errors.acceptTerms ? "acceptTerms-error" : undefined}
                {...register("acceptTerms")}
              />
              {t("auth.register.accept")}
            </label>
            {errors.acceptTerms && (
              <p id="acceptTerms-error" role="alert" className="mt-1.5 text-sm text-rose-700">
                {errors.acceptTerms.message}
              </p>
            )}
          </div>
        </Fieldset>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" size="lg" isLoading={isSubmitting}>
            {t("auth.register.submit")}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              const sample = createSampleRegistration(locale);
              reset({ ...sample, confirmPassword: sample.password, acceptTerms: false });
            }}
          >
            <Wand2 className="h-4 w-4" aria-hidden="true" />
            {t("auth.register.sample")}
          </Button>
        </div>
      </form>
    </AuthCard>
  );
}

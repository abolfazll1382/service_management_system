"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/FormField";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useRedirectWhenSignedIn } from "@/hooks/useRedirectWhenSignedIn";
import { useRevalidateOnLocaleChange } from "@/hooks/useRevalidateOnLocaleChange";
import { useSession } from "@/hooks/useSession";
import { authApi } from "@/lib/api";
import { safeNextPath } from "@/lib/auth/redirect";
import { useSessionStore } from "@/lib/auth/sessionStore";
import { DEMO_CUSTOMERS, DEMO_PASSWORD } from "@/lib/demo/accounts";
import { asDigits } from "@/lib/utils/forms";
import { createCustomerLoginSchema, type CustomerLoginInput } from "@/lib/validation/auth";
import { useFormat, useT } from "@/providers/LocaleProvider";
import { useToast } from "@/providers/ToastProvider";
import { AuthCard } from "./AuthCard";
import { DemoAccounts } from "./DemoAccounts";

export function CustomerLoginForm() {
  const t = useT();
  const format = useFormat();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const { expired } = useSession();
  const next = safeNextPath(useSearchParams().get("next"), "/services");
  const [formError, setFormError] = useState<string | null>(null);

  const schema = useMemo(() => createCustomerLoginSchema(t), [t]);
  const form = useForm<CustomerLoginInput>({ resolver: zodResolver(schema), defaultValues: { nationalId: "", password: "" } });
  const { register, handleSubmit, setValue, formState } = form;
  const { errors, isSubmitting } = formState;
  useRevalidateOnLocaleChange(form);
  useRedirectWhenSignedIn(["customer"], next);

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      useSessionStore.getState().signIn(await authApi.loginCustomer(values));
      toast.success(t("auth.login.success"));
    } catch (error) {
      setFormError(errorMessage(error));
    }
  });

  const registerHref = next === "/services" ? "/register" : `/register?next=${encodeURIComponent(next)}`;

  return (
    <AuthCard
      title={t("auth.login.title")}
      subtitle={t("auth.login.subtitle")}
      footer={
        <>
          {t("auth.login.noAccount")}{" "}
          <Link href={registerHref} className="font-semibold text-tile-700 underline-offset-4 hover:underline">
            {t("common.nav.register")}
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {expired && <Alert tone="warning">{t("errors.unauthenticated")}</Alert>}
        {formError && <Alert tone="danger">{formError}</Alert>}
        <TextField
          id="nationalId"
          label={t("common.fields.nationalId")}
          placeholder={t("auth.placeholders.nationalId")}
          numeric
          maxLength={20}
          autoComplete="username"
          error={errors.nationalId?.message}
          {...register("nationalId", { setValueAs: asDigits })}
        />
        <TextField
          id="password"
          type="password"
          label={t("common.fields.password")}
          autoComplete="current-password"
          error={errors.password?.message}
          {...register("password")}
        />
        <Button type="submit" fullWidth size="lg" isLoading={isSubmitting}>
          {t("auth.login.submit")}
        </Button>
      </form>

      <div className="mt-6">
        <DemoAccounts
          rows={DEMO_CUSTOMERS.map((account) => ({
            key: account.nationalId,
            primary: account.name,
            secondary: format.digits(account.nationalId),
            onUse: () => {
              setValue("nationalId", account.nationalId, { shouldValidate: true });
              setValue("password", DEMO_PASSWORD, { shouldValidate: true });
            },
          }))}
        />
      </div>
    </AuthCard>
  );
}

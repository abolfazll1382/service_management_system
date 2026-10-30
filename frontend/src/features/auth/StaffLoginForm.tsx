"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/FormField";
import { BrandMark } from "@/components/layout/BrandMark";
import { LanguageToggle } from "@/components/layout/LanguageToggle";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useRedirectWhenSignedIn } from "@/hooks/useRedirectWhenSignedIn";
import { useRevalidateOnLocaleChange } from "@/hooks/useRevalidateOnLocaleChange";
import { useSession } from "@/hooks/useSession";
import { authApi } from "@/lib/api";
import { safeNextPath } from "@/lib/auth/redirect";
import { useSessionStore } from "@/lib/auth/sessionStore";
import { DEMO_PASSWORD, DEMO_STAFF } from "@/lib/demo/accounts";
import { getDepartment } from "@/lib/catalog";
import { createStaffLoginSchema, type StaffLoginInput } from "@/lib/validation/auth";
import { useLocale, useT } from "@/providers/LocaleProvider";
import { useToast } from "@/providers/ToastProvider";
import { DemoAccounts } from "./DemoAccounts";

export function StaffLoginForm() {
  const t = useT();
  const { locale } = useLocale();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const { expired } = useSession();
  const next = safeNextPath(useSearchParams().get("next"), "/console");
  const [formError, setFormError] = useState<string | null>(null);

  const schema = useMemo(() => createStaffLoginSchema(t), [t]);
  const form = useForm<StaffLoginInput>({ resolver: zodResolver(schema), defaultValues: { username: "", password: "" } });
  const { register, handleSubmit, setValue, formState } = form;
  const { errors, isSubmitting } = formState;
  useRevalidateOnLocaleChange(form);
  useRedirectWhenSignedIn(["staff", "admin"], next);

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      useSessionStore.getState().signIn(await authApi.loginStaff(values));
      toast.success(t("auth.login.success"));
    } catch (error) {
      setFormError(errorMessage(error));
    }
  });

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <header className="flex items-center justify-between px-4 py-4 sm:px-8">
        <Link href="/" className="flex items-center gap-2.5">
          <BrandMark />
          <span className="text-sm font-bold text-ink-950">{t("common.brand.name")}</span>
        </Link>
        <LanguageToggle />
      </header>

      <main className="mx-auto w-full max-w-md flex-1 px-4 py-8 sm:py-14">
        <h1 className="text-2xl font-extrabold text-ink-950">{t("auth.staffLogin.title")}</h1>
        <p className="mt-1.5 text-sm text-ink-600">{t("auth.staffLogin.subtitle")}</p>

        <div className="mt-6 rounded-2xl border border-ink-200 bg-white p-5 sm:p-7">
          <form onSubmit={onSubmit} noValidate className="space-y-4">
            {expired && <Alert tone="warning">{t("errors.unauthenticated")}</Alert>}
            {formError && <Alert tone="danger">{formError}</Alert>}
            <TextField
              id="username"
              label={t("common.fields.username")}
              placeholder={t("auth.placeholders.username")}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              error={errors.username?.message}
              {...register("username")}
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
              {t("auth.staffLogin.submit")}
            </Button>
          </form>

          <div className="mt-6">
            <DemoAccounts
              rows={DEMO_STAFF.map((account) => ({
                key: account.username,
                primary: account.name[locale],
                secondary:
                  account.role === "admin"
                    ? `${account.username} · ${t("common.role.admin")}`
                    : `${account.username} · ${account.departmentIds.map((id) => getDepartment(id).name[locale]).join("، ")}`,
                onUse: () => {
                  setValue("username", account.username, { shouldValidate: true });
                  setValue("password", DEMO_PASSWORD, { shouldValidate: true });
                },
              }))}
            />
          </div>
        </div>

        <p className="mt-5 text-center text-sm text-ink-600">
          <Link href="/login" className="font-medium text-tile-700 underline-offset-4 hover:underline">
            {t("common.nav.toCustomerSite")}
          </Link>
        </p>
      </main>
    </div>
  );
}

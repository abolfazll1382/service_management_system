"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, CheckCircle2, Send } from "lucide-react";
import { DepartmentBadge } from "@/components/domain/DepartmentBadge";
import { DetailList } from "@/components/domain/DetailList";
import { TrackingCode } from "@/components/domain/TrackingCode";
import { Alert } from "@/components/ui/Alert";
import { Button, buttonStyles } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Ltr } from "@/components/ui/Ltr";
import { TextareaField } from "@/components/ui/FormField";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useRevalidateOnLocaleChange } from "@/hooks/useRevalidateOnLocaleChange";
import { useSession } from "@/hooks/useSession";
import { requestsApi } from "@/lib/api";
import { getDepartment } from "@/lib/catalog";
import { createApplyFormSchema, toServiceDetails, type ApplyFormValues } from "@/lib/validation/request";
import type { ServiceRequest } from "@/types/request";
import type { Service } from "@/types/service";
import { useFormat, useLocale, useT } from "@/providers/LocaleProvider";
import { useToast } from "@/providers/ToastProvider";
import { DynamicField } from "./DynamicField";
import { WizardStepper } from "./WizardStepper";
import { APPLY_STEPS, useApplyWizardStore } from "./applyWizardStore";

export function ApplyForm({ service }: { service: Service }) {
  const t = useT();
  const { locale } = useLocale();
  const format = useFormat();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const { user } = useSession();
  const { step, furthest, next, back, goTo } = useApplyWizardStore();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [created, setCreated] = useState<ServiceRequest | null>(null);

  const schema = useMemo(() => createApplyFormSchema(service, t), [service, t]);
  // The service's fields are only known at runtime, so the schema's static type
  // can't be as precise as ApplyFormValues; the runtime schema is the real guard.
  const form = useForm<ApplyFormValues>({
    resolver: zodResolver(schema) as unknown as Resolver<ApplyFormValues>,
    defaultValues: { description: "", details: {}, confirm: false },
  });
  const { register, handleSubmit, trigger, formState } = form;
  const { errors, isSubmitting } = formState;
  useRevalidateOnLocaleChange(form);

  if (user?.role !== "customer") return null; // the route guard guarantees a customer; this narrows the type

  const stepLabels = [t("request.wizard.steps.applicant"), t("request.wizard.steps.details"), t("request.wizard.steps.review")];
  const detailNames = service.fields.map((field) => `details.${field.key}` as const);
  const isLast = step === APPLY_STEPS.length - 1;

  const goNext = async () => {
    // Moving on from the details step requires that step to be valid.
    if (APPLY_STEPS[step] === "details" && !(await trigger(["description", ...detailNames]))) return;
    next();
  };

  const submit = handleSubmit(
    async ({ description, details }) => {
      setSubmitError(null);
      try {
        const request = await requestsApi.create({
          serviceId: service.id,
          description,
          details: toServiceDetails(service.fields, details),
        });
        setCreated(request);
        toast.success(t("request.wizard.success", { code: format.digits(request.trackingCode) }));
      } catch (error) {
        setSubmitError(errorMessage(error));
      }
    },
    // Something on an earlier step is wrong (e.g. it was edited after review): take them there.
    (invalid) => {
      if (invalid.description || invalid.details) goTo(1);
    },
  );

  if (created) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-5 py-10 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
            <CheckCircle2 className="h-8 w-8" aria-hidden="true" />
          </span>
          <div>
            <h1 className="text-2xl font-extrabold text-ink-950">{t("request.wizard.done.title")}</h1>
            <p className="mt-1.5 max-w-md text-sm text-ink-600">{t("request.wizard.done.body")}</p>
          </div>
          <div className="rounded-xl border border-ink-200 bg-ink-50 px-6 py-4">
            <p className="text-xs font-medium text-ink-500">{t("request.detail.tracking")}</p>
            <TrackingCode code={created.trackingCode} large />
          </div>
          <p className="text-sm text-ink-700">
            {service.title[locale]} · {getDepartment(service.departmentId).name[locale]}
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link href={`/my/requests?open=${created.id}`} className={buttonStyles()}>
              {t("request.wizard.done.viewRequest")}
            </Link>
            <Link href="/services" className={buttonStyles({ variant: "outline" })}>
              {t("request.mine.browse")}
            </Link>
          </div>
        </CardContent>
      </Card>
    );
  }

  const applicant = [
    { label: t("common.fields.fullName"), value: user.fullName },
    { label: t("common.fields.nationalId"), value: <Ltr>{format.digits(user.nationalId)}</Ltr> },
    { label: t("common.fields.phone"), value: <Ltr>{format.digits(user.phone)}</Ltr> },
    { label: t("common.fields.postalCode"), value: <Ltr>{format.digits(user.postalCode)}</Ltr> },
    { label: t("common.fields.address"), value: user.address },
  ];

  return (
    <form onSubmit={submit} noValidate>
      <header className="mb-6">
        <DepartmentBadge departmentId={service.departmentId} />
        <h1 className="mt-1 text-2xl font-extrabold text-ink-950">{t("request.wizard.title", { service: service.title[locale] })}</h1>
      </header>

      <div className="mb-6">
        <WizardStepper labels={stepLabels} current={step} furthest={furthest} onStepClick={goTo} />
      </div>

      <Card>
        <CardContent className="space-y-5 p-5 sm:p-7">
          {APPLY_STEPS[step] === "applicant" && (
            <>
              <div>
                <h2 className="text-lg font-bold text-ink-950">{t("request.wizard.applicant.title")}</h2>
                <p className="mt-1 text-sm text-ink-600">{t("request.wizard.applicant.subtitle")}</p>
              </div>
              <Alert tone="info">{t("request.wizard.applicant.notice")}</Alert>
              <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
                {applicant.map((row) => (
                  <div key={row.label}>
                    <dt className="text-xs font-medium text-ink-500">{row.label}</dt>
                    <dd className="text-sm font-medium text-ink-900">{row.value}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}

          {APPLY_STEPS[step] === "details" && (
            <>
              <div>
                <h2 className="text-lg font-bold text-ink-950">{t("request.wizard.details.title")}</h2>
                <p className="mt-1 text-sm text-ink-600">
                  {t("request.wizard.details.subtitle", { department: getDepartment(service.departmentId).name[locale] })}
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {service.fields.map((field) => (
                  <DynamicField key={field.key} field={field} register={register} errors={errors} />
                ))}
              </div>
              <TextareaField
                id="description"
                label={t("request.wizard.details.description")}
                hint={t("request.wizard.details.descriptionHint")}
                placeholder={t("request.wizard.details.descriptionPlaceholder")}
                rows={5}
                required
                error={errors.description?.message}
                {...register("description")}
              />
            </>
          )}

          {APPLY_STEPS[step] === "review" && (
            <>
              <div>
                <h2 className="text-lg font-bold text-ink-950">{t("request.wizard.review.title")}</h2>
                <p className="mt-1 text-sm text-ink-600">{t("request.wizard.review.subtitle")}</p>
              </div>
              {submitError && <Alert tone="danger">{submitError}</Alert>}
              <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-medium text-ink-500">{t("request.wizard.review.service")}</dt>
                  <dd className="text-sm font-medium text-ink-900">{service.title[locale]}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-ink-500">{t("request.wizard.review.department")}</dt>
                  <dd className="text-sm font-medium text-ink-900">{getDepartment(service.departmentId).name[locale]}</dd>
                </div>
                {applicant.slice(0, 3).map((row) => (
                  <div key={row.label}>
                    <dt className="text-xs font-medium text-ink-500">{row.label}</dt>
                    <dd className="text-sm font-medium text-ink-900">{row.value}</dd>
                  </div>
                ))}
              </dl>
              <hr className="border-ink-100" />
              <DetailList service={service} details={form.getValues("details") as Record<string, string | number>} />
              <div>
                <p className="text-xs font-medium text-ink-500">{t("request.detail.labels.description")}</p>
                <p dir="auto" className="mt-0.5 text-sm leading-7 whitespace-pre-wrap text-ink-900">
                  {form.getValues("description")}
                </p>
              </div>
              <div>
                <label className="flex items-start gap-2.5 text-sm text-ink-800">
                  <input
                    type="checkbox"
                    className="mt-1.5 h-4 w-4 rounded border-ink-300 accent-tile-700"
                    aria-invalid={errors.confirm ? true : undefined}
                    aria-describedby={errors.confirm ? "confirm-error" : undefined}
                    {...register("confirm")}
                  />
                  {t("request.wizard.review.confirm")}
                </label>
                {errors.confirm && (
                  <p id="confirm-error" role="alert" className="mt-1.5 text-sm text-rose-700">
                    {errors.confirm.message}
                  </p>
                )}
              </div>
            </>
          )}

          <div className="flex items-center justify-between gap-3 border-t border-ink-100 pt-5">
            <Button type="button" variant="outline" onClick={back} disabled={step === 0 || isSubmitting}>
              <ArrowLeft className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
              {t("common.actions.back")}
            </Button>
            {isLast ? (
              <Button type="submit" isLoading={isSubmitting}>
                <Send className="h-4 w-4 rtl:-scale-x-100" aria-hidden="true" />
                {t("request.wizard.submit")}
              </Button>
            ) : (
              <Button type="button" onClick={goNext}>
                {t("common.actions.next")}
                <ArrowRight className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </form>
  );
}

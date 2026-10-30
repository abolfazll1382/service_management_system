"use client";

import type { ReactNode } from "react";

import { DepartmentBadge } from "@/components/domain/DepartmentBadge";
import { DetailList } from "@/components/domain/DetailList";
import { RequestTimeline } from "@/components/domain/RequestTimeline";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { TrackingCode } from "@/components/domain/TrackingCode";
import { Ltr } from "@/components/ui/Ltr";
import { findService } from "@/lib/catalog";
import { useFormat, useLocale, useT } from "@/providers/LocaleProvider";
import type { ServiceRequest } from "@/types/request";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-3 border-b border-ink-100 pb-1.5 text-sm font-bold text-ink-900">{title}</h3>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-ink-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink-900">{children}</dd>
    </div>
  );
}

/**
 * One request, laid out the same way for the applicant and for staff: who and
 * what, the answers given, and the activity so far. Staff additionally see
 * the applicant's contact details; internal notes only appear when the
 * server included them (it only does so for staff).
 */
export function RequestDetails({ request, showApplicant = false }: { request: ServiceRequest; showApplicant?: boolean }) {
  const t = useT();
  const { locale } = useLocale();
  const format = useFormat();
  const service = findService(request.serviceId);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-xl font-bold text-ink-950">{service ? service.title[locale] : request.serviceId}</h2>
          <div className="mt-1 text-sm text-ink-600">
            <span className="me-1.5">{t("request.detail.tracking")}:</span>
            <TrackingCode code={request.trackingCode} />
          </div>
        </div>
        <StatusBadge status={request.status} />
      </div>

      <Section title={t("request.detail.sections.summary")}>
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
          <Field label={t("request.detail.labels.department")}>
            <DepartmentBadge departmentId={request.departmentId} className="text-ink-900" />
          </Field>
          <Field label={t("request.detail.labels.submitted")}>{format.dateTime(request.submittedAt)}</Field>
          <Field label={t("request.detail.labels.assignedTo")}>
            {request.assignee ? request.assignee.name[locale] : <span className="text-ink-500">{t("request.detail.unassigned")}</span>}
          </Field>
          {showApplicant && (
            <>
              <Field label={t("staff.work.customer")}>{request.customer.fullName}</Field>
              <Field label={t("common.fields.nationalId")}>
                <Ltr>{format.digits(request.customer.nationalId)}</Ltr>
              </Field>
              <Field label={t("common.fields.phone")}>
                <Ltr>{format.digits(request.customer.phone)}</Ltr>
              </Field>
            </>
          )}
        </dl>
      </Section>

      <Section title={t("request.detail.sections.answers")}>
        <div className="space-y-4">
          {service && <DetailList service={service} details={request.details} />}
          <div>
            <p className="text-xs font-medium text-ink-500">{t("request.detail.labels.description")}</p>
            {/* dir="auto": the applicant may have written in either script; punctuation must land on the correct side. */}
            <p dir="auto" className="mt-0.5 text-sm leading-7 whitespace-pre-wrap text-ink-900">
              {request.description}
            </p>
          </div>
        </div>
      </Section>

      <Section title={t("request.detail.sections.activity")}>
        <RequestTimeline events={request.timeline} />
      </Section>
    </div>
  );
}

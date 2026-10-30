"use client";

import Link from "next/link";
import { DepartmentIcon } from "@/components/domain/DepartmentBadge";
import { buttonStyles } from "@/components/ui/Button";
import { useSession } from "@/hooks/useSession";
import { DEPARTMENTS, servicesInDepartment } from "@/lib/catalog";
import { useFormat, useLocale, useT } from "@/providers/LocaleProvider";

export function HomeView() {
  const t = useT();
  const { locale } = useLocale();
  const format = useFormat();
  const { user, hydrated } = useSession();

  const steps = [
    { title: t("catalog.steps.register.title"), body: t("catalog.steps.register.body") },
    { title: t("catalog.steps.choose.title"), body: t("catalog.steps.choose.body") },
    { title: t("catalog.steps.track.title"), body: t("catalog.steps.track.body") },
  ];

  return (
    <>
      <section className="relative overflow-hidden bg-ink-900 text-white">
        <div className="pattern-stars absolute inset-0" aria-hidden="true" />
        <div className="relative mx-auto max-w-6xl px-4 pt-16 pb-32 sm:px-6 sm:pt-24 sm:pb-40">
          <h1 className="max-w-3xl text-3xl leading-snug font-extrabold text-balance sm:text-5xl sm:leading-tight">
            {t("catalog.hero.title")}
          </h1>
          <p className="mt-5 max-w-2xl text-base text-ink-200 sm:text-lg">{t("catalog.hero.subtitle")}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/services" className={buttonStyles({ size: "lg", className: "bg-white text-ink-950 hover:bg-ink-100" })}>
              {t("catalog.hero.browse")}
            </Link>
            {hydrated && user === null && (
              <Link
                href="/register"
                className={buttonStyles({
                  variant: "outline",
                  size: "lg",
                  className: "border-white/35 bg-transparent text-white hover:border-white/60 hover:bg-white/10",
                })}
              >
                {t("common.nav.register")}
              </Link>
            )}
            {hydrated && user?.role === "customer" && (
              <Link
                href="/my/requests"
                className={buttonStyles({
                  variant: "outline",
                  size: "lg",
                  className: "border-white/35 bg-transparent text-white hover:border-white/60 hover:bg-white/10",
                })}
              >
                {t("common.nav.myRequests")}
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* The four departments are the real front door: each one leads to its services. */}
      <section className="relative mx-auto -mt-20 max-w-6xl px-4 sm:-mt-24 sm:px-6">
        <h2 className="sr-only">{t("catalog.list.title")}</h2>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {DEPARTMENTS.map((department) => (
            <li key={department.id}>
              <Link
                href={`/services?department=${department.id}`}
                className="group flex h-full flex-col rounded-2xl border border-ink-200 bg-white p-5 transition-colors hover:border-tile-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tile-600"
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-tile-50 text-tile-700 transition-colors group-hover:bg-tile-100">
                  <DepartmentIcon departmentId={department.id} className="h-6 w-6" />
                </span>
                <h3 className="mt-4 text-base font-bold text-ink-950">{department.name[locale]}</h3>
                <p className="mt-1 flex-1 text-sm text-ink-600">{department.description[locale]}</p>
                <p className="mt-4 text-sm font-medium text-tile-700">
                  {t("catalog.home.serviceCount", { count: servicesInDepartment(department.id).length })}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <h2 className="text-xl font-bold text-ink-950">{t("catalog.steps.title")}</h2>
        {/* A real sequence, so the numbers are earned. */}
        <ol className="mt-6 grid gap-8 md:grid-cols-3">
          {steps.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink-900 text-sm font-bold text-white">
                {format.number(index + 1)}
              </span>
              <div>
                <h3 className="font-semibold text-ink-950">{step.title}</h3>
                <p className="mt-1 text-sm text-ink-600">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}

"use client";

import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { buttonStyles } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { useT } from "@/providers/LocaleProvider";

/** Signed in, but this account's role or departments don't include this page. */
export function ForbiddenState({ homeHref, homeLabel }: { homeHref: string; homeLabel?: string }) {
  const t = useT();
  return (
    <EmptyState
      icon={ShieldAlert}
      title={t("common.forbidden.title")}
      body={t("common.forbidden.body")}
      action={
        <Link href={homeHref} className={buttonStyles({ variant: "outline" })}>
          {homeLabel ?? t("common.forbidden.back")}
        </Link>
      }
    />
  );
}

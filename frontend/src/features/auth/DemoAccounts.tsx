"use client";

import type { ReactNode } from "react";
import { KeyRound } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { DEMO_PASSWORD } from "@/lib/demo/accounts";
import { useT } from "@/providers/LocaleProvider";

export interface DemoRow {
  key: string;
  primary: ReactNode;
  secondary: ReactNode;
  onUse: () => void;
}

/**
 * Because this is a demonstration, the sign-in pages list the sample
 * accounts and fill the form for you. A real deployment would not have
 * this box — which is why it lives in its own component, easy to delete.
 */
export function DemoAccounts({ rows }: { rows: readonly DemoRow[] }) {
  const t = useT();
  return (
    <section aria-labelledby="demo-accounts-title" className="rounded-xl border border-dashed border-ink-300 bg-ink-50/60 p-4">
      <h2 id="demo-accounts-title" className="flex items-center gap-2 text-sm font-semibold text-ink-900">
        <KeyRound className="h-4 w-4 text-ink-500" aria-hidden="true" />
        {t("auth.demoAccounts.title")}
      </h2>
      <p className="mt-1 text-xs text-ink-600">{t("auth.demoAccounts.note", { password: DEMO_PASSWORD })}</p>
      <ul className="mt-3 divide-y divide-ink-100">
        {rows.map((row) => (
          <li key={row.key} className="flex items-center justify-between gap-3 py-2">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink-900">{row.primary}</p>
              <p className="truncate text-xs text-ink-500">{row.secondary}</p>
            </div>
            <Button variant="outline" size="sm" onClick={row.onUse}>
              {t("auth.demoAccounts.use")}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}

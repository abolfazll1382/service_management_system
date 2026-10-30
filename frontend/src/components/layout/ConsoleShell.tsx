"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ExternalLink, Inbox, LogOut, RotateCcw, ScrollText, ToggleRight, Users, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { DepartmentBadge } from "@/components/domain/DepartmentBadge";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { useCan, useSession, useSignOut } from "@/hooks/useSession";
import { demoApi } from "@/lib/api";
import { visibleDepartments } from "@/lib/auth/policies";
import { cn } from "@/lib/utils/cn";
import { displayName } from "@/types/user";
import { useLocale, useT } from "@/providers/LocaleProvider";
import { useToast } from "@/providers/ToastProvider";
import { BrandMark } from "./BrandMark";
import { LanguageToggle } from "./LanguageToggle";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

/**
 * The staff console frame: a dark sidebar on large screens, a scrolling nav
 * row on small ones. Navigation entries are filtered by what the signed-in
 * account may do, so staff never see "Team" or "Audit log" — and if they
 * type the URL anyway, the page's own guard and the server still say no.
 */
export function ConsoleShell({ children }: { children: ReactNode }) {
  const t = useT();
  const { locale } = useLocale();
  const pathname = usePathname();
  const { user } = useSession();
  const can = useCan();
  const signOut = useSignOut();
  const toast = useToast();
  const errorMessage = useErrorMessage();
  const [confirmReset, setConfirmReset] = useState(false);
  const [resetting, setResetting] = useState(false);
  // Bumping the key remounts the page below, so every list refetches after a reset.
  const [dataVersion, setDataVersion] = useState(0);

  if (!user) return null; // RequireAuth guarantees a user; this narrows the type

  const items: NavItem[] = [
    { href: "/console", label: t("staff.nav.requests"), icon: Inbox },
    ...(can("staff.manage") ? [{ href: "/console/team", label: t("staff.nav.team"), icon: Users }] : []),
    ...(can("service.manage") ? [{ href: "/console/services", label: t("staff.nav.services"), icon: ToggleRight }] : []),
    ...(can("audit.read") ? [{ href: "/console/audit", label: t("staff.nav.audit"), icon: ScrollText }] : []),
  ];
  const isActive = (href: string) => (href === "/console" ? pathname === "/console" : pathname.startsWith(href));
  const departments = visibleDepartments(user);

  const reset = async () => {
    setResetting(true);
    try {
      await demoApi.reset();
      setConfirmReset(false);
      setDataVersion((version) => version + 1);
      toast.success(t("staff.reset.done"));
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[17rem_minmax(0,1fr)]">
      <aside className="hidden flex-col bg-ink-900 text-ink-100 lg:flex">
        <div className="sticky top-0 flex h-dvh flex-col">
          <div className="flex items-center gap-3 px-5 py-5">
            <BrandMark />
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-white">{t("common.brand.short")}</p>
              <p className="text-xs text-ink-300">{t("common.brand.console")}</p>
            </div>
          </div>

          <nav aria-label={t("common.nav.menu")} className="flex-1 space-y-1 px-3 py-2">
            {items.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-tile-300",
                  isActive(href) ? "bg-white/12 text-white" : "text-ink-200 hover:bg-white/8 hover:text-white",
                )}
              >
                <Icon className="h-4.5 w-4.5" aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>

          <div className="space-y-3 border-t border-white/10 px-5 py-4">
            {can("demo.reset") && (
              <button
                type="button"
                onClick={() => setConfirmReset(true)}
                className="flex w-full items-center gap-2 rounded-md px-1 py-1 text-sm text-ink-300 hover:text-white"
              >
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
                {t("staff.sidebar.resetDemo")}
              </button>
            )}
            <div>
              <p className="truncate text-sm font-semibold text-white">{displayName(user, locale)}</p>
              <p className="text-xs text-ink-300">{t(`common.role.${user.role}`)}</p>
            </div>
            <button
              type="button"
              onClick={() => void signOut("/console/login")}
              className="flex items-center gap-2 text-sm text-ink-300 hover:text-white"
            >
              <LogOut className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
              {t("common.nav.signOut")}
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="border-b border-ink-200 bg-white">
          <div className="flex min-h-14 flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2 sm:px-6 lg:px-8">
            <div className="flex items-center gap-2.5 lg:hidden">
              <BrandMark className="h-8 w-8" />
              <span className="text-sm font-bold text-ink-950">{t("common.brand.console")}</span>
            </div>

            <div className="hidden min-w-0 flex-1 items-center gap-2 lg:flex">
              <span className="text-sm text-ink-500">{t("staff.topbar.departments")}:</span>
              {user.role === "admin" ? (
                <Badge tone="info">{t("staff.topbar.allDepartments")}</Badge>
              ) : (
                departments.map((id) => <DepartmentBadge key={id} departmentId={id} className="rounded-full bg-ink-50 px-2.5 py-0.5" />)
              )}
            </div>

            <div className="ms-auto flex items-center gap-2">
              <Link href="/" className="hidden items-center gap-1.5 text-sm text-ink-600 hover:text-ink-950 sm:inline-flex">
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
                {t("common.nav.toCustomerSite")}
              </Link>
              <LanguageToggle />
              <Button variant="ghost" size="sm" className="lg:hidden" onClick={() => void signOut("/console/login")}>
                <LogOut className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
                <span className="sr-only">{t("common.nav.signOut")}</span>
              </Button>
            </div>
          </div>

          <nav aria-label={t("common.nav.menu")} className="flex gap-1 overflow-x-auto border-t border-ink-100 px-3 py-1.5 lg:hidden">
            {items.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "inline-flex shrink-0 items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium",
                  isActive(href) ? "bg-ink-900 text-white" : "text-ink-700 hover:bg-ink-100",
                )}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>
        </header>

        <main key={dataVersion} className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>

      <ConfirmDialog
        isOpen={confirmReset}
        onClose={() => setConfirmReset(false)}
        onConfirm={reset}
        isLoading={resetting}
        danger
        title={t("staff.reset.title")}
        confirmLabel={t("staff.reset.confirm")}
      >
        {t("staff.reset.body")}
      </ConfirmDialog>
    </div>
  );
}

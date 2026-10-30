"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, Menu, X } from "lucide-react";
import { Button, buttonStyles } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Spinner";
import { useSession, useSignOut } from "@/hooks/useSession";
import { cn } from "@/lib/utils/cn";
import { displayName } from "@/types/user";
import { useLocale, useT } from "@/providers/LocaleProvider";
import { BrandMark } from "./BrandMark";
import { LanguageToggle } from "./LanguageToggle";

interface NavItem {
  href: string;
  label: string;
}

export function SiteHeader() {
  const t = useT();
  const { locale } = useLocale();
  const pathname = usePathname();
  const { user, hydrated } = useSession();
  const signOut = useSignOut();
  const [menuOpen, setMenuOpen] = useState(false);

  const items: NavItem[] = [
    { href: "/", label: t("common.nav.home") },
    { href: "/services", label: t("common.nav.services") },
    ...(user?.role === "customer" ? [{ href: "/my/requests", label: t("common.nav.myRequests") }] : []),
  ];
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  const close = () => setMenuOpen(false);

  const authArea = !hydrated ? (
    <Skeleton className="h-9 w-40" />
  ) : user === null ? (
    <>
      <Link href="/login" onClick={close} className={buttonStyles({ variant: "outline" })}>
        {t("common.nav.signIn")}
      </Link>
      <Link href="/register" onClick={close} className={buttonStyles({ variant: "primary" })}>
        {t("common.nav.register")}
      </Link>
    </>
  ) : (
    <>
      {user.role !== "customer" && (
        <Link href="/console" onClick={close} className={buttonStyles({ variant: "outline" })}>
          {t("common.nav.toConsole")}
        </Link>
      )}
      <span className="max-w-40 truncate text-sm font-medium text-ink-800">{displayName(user, locale)}</span>
      <Button variant="ghost" onClick={() => void signOut("/")}>
        <LogOut className="h-4 w-4 rtl:rotate-180" aria-hidden="true" />
        {t("common.nav.signOut")}
      </Button>
    </>
  );

  return (
    <header className="sticky top-0 z-40 border-b border-ink-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex min-w-0 items-center gap-2.5" onClick={close}>
          <BrandMark />
          <span className="truncate text-base font-bold text-ink-950">
            <span className="hidden sm:inline">{t("common.brand.name")}</span>
            <span className="sm:hidden">{t("common.brand.short")}</span>
          </span>
        </Link>

        <nav aria-label={t("common.nav.menu")} className="ms-6 hidden items-center gap-1 md:flex">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(item.href) ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                isActive(item.href) ? "bg-ink-100 text-ink-950" : "text-ink-600 hover:bg-ink-50 hover:text-ink-900",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ms-auto flex items-center gap-2">
          <LanguageToggle />
          <div className="hidden items-center gap-2 md:flex">{authArea}</div>
          <button
            type="button"
            className="rounded-md p-2 text-ink-700 hover:bg-ink-100 md:hidden"
            aria-expanded={menuOpen}
            aria-controls="site-mobile-menu"
            aria-label={t("common.nav.menu")}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <X className="h-5 w-5" aria-hidden="true" /> : <Menu className="h-5 w-5" aria-hidden="true" />}
          </button>
        </div>
      </div>

      {menuOpen && (
        <div id="site-mobile-menu" className="border-t border-ink-100 bg-white px-4 pb-4 md:hidden">
          <nav aria-label={t("common.nav.menu")} className="flex flex-col py-2">
            {items.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={close}
                aria-current={isActive(item.href) ? "page" : undefined}
                className={cn("rounded-md px-3 py-2.5 text-sm font-medium", isActive(item.href) ? "bg-ink-100 text-ink-950" : "text-ink-700")}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="flex flex-wrap items-center gap-2 border-t border-ink-100 pt-3">{authArea}</div>
        </div>
      )}
    </header>
  );
}

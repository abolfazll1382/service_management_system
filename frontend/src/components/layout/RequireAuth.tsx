"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { LoadingBlock } from "@/components/ui/Spinner";
import { useSession } from "@/hooks/useSession";
import { loginUrl } from "@/lib/auth/redirect";
import type { Role } from "@/types/user";
import { ForbiddenState } from "./ForbiddenState";

interface RequireAuthProps {
  /** Roles allowed to see this area. */
  roles: readonly Role[];
  /** Where to send someone who isn't signed in. */
  loginPath: string;
  /** Where "go back" leads for someone signed in with the wrong role. */
  forbiddenHome: string;
  children: ReactNode;
}

/**
 * Route guard. Three outcomes: not signed in → sign-in page (remembering
 * where they were going); signed in with the wrong role → an explanation;
 * allowed → the page. Until the stored session has been read it shows a
 * neutral loader, so a signed-in person is never bounced to sign-in for a frame.
 *
 * This only shapes what the browser shows. Every API call is checked again
 * by the server, so skipping a guard exposes an empty page, never data.
 */
export function RequireAuth({ roles, loginPath, forbiddenHome, children }: RequireAuthProps) {
  const { user, hydrated } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (hydrated && user === null) router.replace(loginUrl(loginPath, pathname));
  }, [hydrated, user, router, loginPath, pathname]);

  if (!hydrated || user === null) return <LoadingBlock className="min-h-[50vh]" />;
  if (!roles.includes(user.role)) return <ForbiddenState homeHref={forbiddenHome} />;
  return children;
}

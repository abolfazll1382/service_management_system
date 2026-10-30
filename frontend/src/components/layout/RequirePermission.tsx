"use client";

import type { ReactNode } from "react";
import { useCan } from "@/hooks/useSession";
import type { Action } from "@/lib/auth/policies";
import { ForbiddenState } from "./ForbiddenState";

/** Page-level check for admin-only screens: staff who type the URL get an explanation, not the page. */
export function RequirePermission({ action, children }: { action: Action; children: ReactNode }) {
  const can = useCan();
  if (!can(action)) return <ForbiddenState homeHref="/console" />;
  return children;
}

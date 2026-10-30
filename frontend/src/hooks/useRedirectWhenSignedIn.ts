"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import type { Role } from "@/types/user";
import { useSession } from "./useSession";

/**
 * Sign-in and registration pages have nothing to offer someone who is
 * already signed in (or who just did): send them on. One mechanism covers
 * both "arrived while signed in" and "signed in a moment ago".
 */
export function useRedirectWhenSignedIn(roles: readonly Role[], target: string) {
  const { user, hydrated } = useSession();
  const router = useRouter();
  useEffect(() => {
    if (hydrated && user !== null && roles.includes(user.role)) router.replace(target);
  }, [hydrated, user, roles, router, target]);
}

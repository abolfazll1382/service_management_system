import type { ReactNode } from "react";
import { ConsoleShell } from "@/components/layout/ConsoleShell";
import { RequireAuth } from "@/components/layout/RequireAuth";

/** Everything under /console except the sign-in page: staff and admins only. */
export default function ConsoleAppLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth roles={["staff", "admin"]} loginPath="/console/login" forbiddenHome="/">
      <ConsoleShell>{children}</ConsoleShell>
    </RequireAuth>
  );
}

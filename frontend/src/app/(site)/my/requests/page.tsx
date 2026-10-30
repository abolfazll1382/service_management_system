import { Suspense } from "react";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { MyRequestsView } from "@/features/requests/MyRequestsView";
import { titleFor } from "@/lib/i18n/page-metadata";

export const generateMetadata = () => titleFor("request.mine.title");

export default function MyRequestsPage() {
  return (
    <RequireAuth roles={["customer"]} loginPath="/login" forbiddenHome="/services">
      <Suspense>
        <MyRequestsView />
      </Suspense>
    </RequireAuth>
  );
}

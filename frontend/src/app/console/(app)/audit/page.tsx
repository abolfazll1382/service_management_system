import { RequirePermission } from "@/components/layout/RequirePermission";
import { AuditView } from "@/features/console/AuditView";
import { titleFor } from "@/lib/i18n/page-metadata";

export const generateMetadata = () => titleFor("staff.audit.title");

export default function AuditPage() {
  return (
    <RequirePermission action="audit.read">
      <AuditView />
    </RequirePermission>
  );
}

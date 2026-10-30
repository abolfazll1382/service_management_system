import { RequirePermission } from "@/components/layout/RequirePermission";
import { ServiceAvailabilityView } from "@/features/console/ServiceAvailabilityView";
import { titleFor } from "@/lib/i18n/page-metadata";

export const generateMetadata = () => titleFor("staff.services.title");

export default function ServiceAvailabilityPage() {
  return (
    <RequirePermission action="service.manage">
      <ServiceAvailabilityView />
    </RequirePermission>
  );
}

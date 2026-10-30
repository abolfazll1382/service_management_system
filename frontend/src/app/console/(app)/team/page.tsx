import { RequirePermission } from "@/components/layout/RequirePermission";
import { TeamView } from "@/features/console/TeamView";
import { titleFor } from "@/lib/i18n/page-metadata";

export const generateMetadata = () => titleFor("staff.team.title");

export default function TeamPage() {
  return (
    <RequirePermission action="staff.manage">
      <TeamView />
    </RequirePermission>
  );
}

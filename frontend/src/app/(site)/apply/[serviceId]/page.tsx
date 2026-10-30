import { RequireAuth } from "@/components/layout/RequireAuth";
import { ApplyWizard } from "@/features/apply/ApplyWizard";
import { titleFor } from "@/lib/i18n/page-metadata";

export const generateMetadata = () => titleFor("catalog.detail.apply");

type Params = { params: Promise<{ serviceId: string }> };

export default async function ApplyPage({ params }: Params) {
  const { serviceId } = await params;
  return (
    // Registration comes first: anyone not signed in is sent to the sign-in page and brought back here.
    <RequireAuth roles={["customer"]} loginPath="/login" forbiddenHome="/services">
      <ApplyWizard serviceId={serviceId} />
    </RequireAuth>
  );
}

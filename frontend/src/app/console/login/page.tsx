import { Suspense } from "react";
import { StaffLoginForm } from "@/features/auth/StaffLoginForm";
import { titleFor } from "@/lib/i18n/page-metadata";

export const generateMetadata = () => titleFor("auth.staffLogin.title");

export default function StaffLoginPage() {
  return (
    <Suspense>
      <StaffLoginForm />
    </Suspense>
  );
}

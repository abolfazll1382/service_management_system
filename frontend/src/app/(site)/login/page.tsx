import { Suspense } from "react";
import { CustomerLoginForm } from "@/features/auth/CustomerLoginForm";
import { titleFor } from "@/lib/i18n/page-metadata";

export const generateMetadata = () => titleFor("auth.login.title");

export default function LoginPage() {
  return (
    <Suspense>
      <CustomerLoginForm />
    </Suspense>
  );
}

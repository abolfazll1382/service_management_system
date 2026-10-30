import { Suspense } from "react";
import { RegisterForm } from "@/features/auth/RegisterForm";
import { titleFor } from "@/lib/i18n/page-metadata";

export const generateMetadata = () => titleFor("auth.register.title");

export default function RegisterPage() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  );
}

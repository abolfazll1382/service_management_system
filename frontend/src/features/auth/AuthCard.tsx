import type { ReactNode } from "react";

interface AuthCardProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}

/** The frame shared by every sign-in and registration page. */
export function AuthCard({ title, subtitle, children, footer, wide }: AuthCardProps) {
  return (
    <div className={`mx-auto w-full px-4 py-10 sm:py-14 ${wide ? "max-w-2xl" : "max-w-md"}`}>
      <h1 className="text-2xl font-extrabold text-ink-950">{title}</h1>
      <p className="mt-1.5 text-sm text-ink-600">{subtitle}</p>
      <div className="mt-6 rounded-2xl border border-ink-200 bg-white p-5 sm:p-7">{children}</div>
      {footer && <div className="mt-5 text-center text-sm text-ink-600">{footer}</div>}
    </div>
  );
}

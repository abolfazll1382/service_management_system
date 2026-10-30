import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const TONES = {
  info: { box: "border-sky-200 bg-sky-50 text-sky-950", icon: Info, iconColor: "text-sky-600" },
  success: { box: "border-emerald-200 bg-emerald-50 text-emerald-950", icon: CheckCircle2, iconColor: "text-emerald-600" },
  warning: { box: "border-saffron-300 bg-saffron-50 text-ink-900", icon: AlertTriangle, iconColor: "text-saffron-500" },
  danger: { box: "border-rose-200 bg-rose-50 text-rose-950", icon: XCircle, iconColor: "text-rose-600" },
} as const;

interface AlertProps {
  tone?: keyof typeof TONES;
  title?: string;
  children?: ReactNode;
  className?: string;
}

export function Alert({ tone = "info", title, children, className }: AlertProps) {
  const { box, icon: Icon, iconColor } = TONES[tone];
  return (
    <div role={tone === "danger" ? "alert" : undefined} className={cn("flex gap-3 rounded-lg border p-3.5 text-sm", box, className)}>
      <Icon className={cn("mt-0.5 h-4.5 w-4.5 shrink-0", iconColor)} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn(title && "mt-0.5")}>{children}</div>}
      </div>
    </div>
  );
}

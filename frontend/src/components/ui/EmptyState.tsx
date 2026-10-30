import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  body?: string;
  action?: ReactNode;
}

/** Emptiness is an invitation: say what's missing and offer the next step. */
export function EmptyState({ icon: Icon = Inbox, title, body, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-ink-100 text-ink-500">
        <Icon className="h-6 w-6" aria-hidden="true" />
      </span>
      <h2 className="mt-4 text-base font-semibold text-ink-900">{title}</h2>
      {body && <p className="mt-1 max-w-sm text-sm text-ink-600">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

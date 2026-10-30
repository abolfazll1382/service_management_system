"use client";

import { ArrowRightLeft, CircleDot, MessageSquare, SendHorizontal, UserCheck, UserMinus, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils/cn";
import { useFormat, useLocale, useT } from "@/providers/LocaleProvider";
import type { TimelineEvent } from "@/types/request";

const ICONS: Record<TimelineEvent["kind"], LucideIcon> = {
  submitted: SendHorizontal,
  status_changed: ArrowRightLeft,
  assigned: UserCheck,
  message: MessageSquare,
};

/**
 * The activity history, oldest first. One component for both sides: staff
 * see internal notes (the server only sends them to staff), customers never
 * receive them, so this renders whatever it is given.
 */
export function RequestTimeline({ events }: { events: readonly TimelineEvent[] }) {
  const t = useT();
  const { locale } = useLocale();
  const format = useFormat();

  const describe = (event: TimelineEvent): string => {
    const actor = event.actor.name[locale];
    switch (event.kind) {
      case "submitted":
        return t("request.timeline.submitted", { actor });
      case "status_changed":
        return t("request.timeline.status_changed", {
          actor,
          from: t(`common.status.${event.from}`),
          to: t(`common.status.${event.to}`),
        });
      case "assigned":
        return event.assignee
          ? t("request.timeline.assigned", { actor, assignee: event.assignee.name[locale] })
          : t("request.timeline.unassigned", { actor });
      case "message":
        return t("request.timeline.message", { actor });
    }
  };

  return (
    <ol className="relative space-y-5">
      {events.map((event, index) => {
        const Icon = event.kind === "assigned" && event.assignee === null ? UserMinus : ICONS[event.kind];
        const isInternal = event.kind === "message" && event.visibility === "internal";
        const isLast = index === events.length - 1;
        return (
          <li key={event.id} className="relative flex gap-3">
            {/* The rail connects events in order — it's the one place a line carries meaning. */}
            {!isLast && <span aria-hidden="true" className="absolute start-4 top-9 -bottom-5 w-px -translate-x-1/2 bg-ink-200 rtl:translate-x-1/2" />}
            <span
              className={cn(
                "relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
                isInternal ? "border-saffron-300 bg-saffron-50 text-saffron-700" : "border-ink-200 bg-white text-ink-500",
              )}
            >
              {index === 0 ? <CircleDot className="h-4 w-4" aria-hidden="true" /> : <Icon className="h-4 w-4" aria-hidden="true" />}
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <p className="text-sm text-ink-900">
                {describe(event)}
                {isInternal && (
                  <Badge tone="attention" className="ms-2">
                    {t("request.timeline.internal")}
                  </Badge>
                )}
              </p>
              <time dateTime={event.at} className="text-xs text-ink-500">
                {format.dateTime(event.at)}
              </time>
              {event.kind === "message" && (
                <p
                  dir="auto"
                  className={cn(
                    "mt-2 rounded-lg border px-3 py-2 text-sm leading-7 whitespace-pre-wrap",
                    isInternal ? "border-saffron-200 bg-saffron-50/60 text-ink-900" : "border-ink-100 bg-ink-50 text-ink-800",
                  )}
                >
                  {event.body}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

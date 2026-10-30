"use client";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { useT } from "@/providers/LocaleProvider";
import type { RequestStatus } from "@/types/request";

/**
 * Colour is semantic: saffron = someone must act, blue = underway, green and
 * red = outcomes, grey = filed away. The label always carries the meaning too.
 */
const TONES: Record<RequestStatus, BadgeTone> = {
  pending_review: "warning",
  in_progress: "info",
  needs_correction: "attention",
  approved: "success",
  rejected: "danger",
  closed: "closed",
};

export function StatusBadge({ status }: { status: RequestStatus }) {
  const t = useT();
  return <Badge tone={TONES[status]}>{t(`common.status.${status}`)}</Badge>;
}

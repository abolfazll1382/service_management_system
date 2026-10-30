import type { Paged } from "@/types/api";
import type { AuditEntry } from "@/types/audit";
import { z } from "zod";
import { createId } from "@/lib/utils/id";
import { readDb, nowIso } from "./db";
import { authorize, requireActor, type ServerContext } from "./session";
import { parseInput } from "./validate";

/** Enough history to look real, bounded so localStorage never fills up. */
const MAX_ENTRIES = 500;

export type NewAuditEntry = Omit<AuditEntry, "id" | "at">;

/** Returns a NEW array with the entry appended; callers write it back. */
export function appendAudit(audit: readonly AuditEntry[], entry: NewAuditEntry): AuditEntry[] {
  const next: AuditEntry = { id: createId(), at: nowIso(), ...entry };
  return [...audit, next].slice(-MAX_ENTRIES);
}

const auditQuerySchema = z.object({
  page: z.number().int().min(1).optional(),
  pageSize: z.number().int().min(1).max(100).optional(),
});

export function listAudit(ctx: ServerContext, query: unknown): Paged<AuditEntry> {
  const actor = requireActor(ctx);
  authorize(actor, "audit.read");
  const { page = 1, pageSize = 15 } = parseInput(auditQuerySchema, query ?? {});
  const newestFirst = [...readDb().audit].reverse();
  const start = (page - 1) * pageSize;
  return { items: newestFirst.slice(start, start + pageSize), total: newestFirst.length, page, pageSize };
}

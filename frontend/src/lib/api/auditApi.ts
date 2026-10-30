import type { Paged } from "@/types/api";
import type { AuditEntry } from "@/types/audit";
import * as server from "@/lib/mock-server/audit";
import { mockRequest } from "./mockClient";

export const auditApi = {
  list: (query: { page?: number; pageSize?: number } = {}): Promise<Paged<AuditEntry>> =>
    mockRequest((ctx) => server.listAudit(ctx, query)),
};

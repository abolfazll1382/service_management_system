import { ApiError } from "@/types/api";
import type { ServiceListing } from "@/types/service";
import { findService, SERVICES } from "@/lib/catalog";
import { appendAudit } from "./audit";
import { readDb, writeDb } from "./db";
import { authorize, requireActor, type ServerContext } from "./session";
import { toActorRef } from "@/types/user";

/** A service with no entry is open; only an explicit `false` closes it. */
export function isServiceActive(serviceId: string): boolean {
  return readDb().serviceActive[serviceId] !== false;
}

/** Public: browsing the catalog needs no account. */
export function listServices(): ServiceListing[] {
  const { serviceActive } = readDb();
  return SERVICES.map((service) => ({ ...service, isActive: serviceActive[service.id] !== false }));
}

export function getService(serviceId: string): ServiceListing {
  const service = findService(serviceId);
  if (!service) throw new ApiError("not_found");
  return { ...service, isActive: isServiceActive(service.id) };
}

export function setServiceActive(ctx: ServerContext, serviceId: string, isActive: boolean): ServiceListing {
  const actor = requireActor(ctx);
  authorize(actor, "service.manage");
  const service = findService(serviceId);
  if (!service) throw new ApiError("not_found");

  const db = readDb();
  writeDb({
    serviceActive: { ...db.serviceActive, [service.id]: isActive },
    audit: appendAudit(db.audit, {
      actor: toActorRef(actor),
      action: isActive ? "service_resumed" : "service_paused",
      target: service.id,
    }),
  });
  return { ...service, isActive };
}

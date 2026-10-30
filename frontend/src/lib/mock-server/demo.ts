import { createSeedData } from "@/lib/store/seed";
import { toActorRef } from "@/types/user";
import { appendAudit } from "./audit";
import { readDb, resetDb } from "./db";
import { authorize, requireActor, type ServerContext } from "./session";

/**
 * Puts the demo back to its starting data. The caller's own session is kept
 * so the administrator who pressed the button isn't signed out of the page
 * they are looking at; every OTHER session ends, which is what a reset means.
 */
export function resetDemo(ctx: ServerContext): void {
  const actor = requireActor(ctx);
  authorize(actor, "demo.reset");
  const keep = ctx.token === null ? undefined : readDb().sessions[ctx.token];

  resetDb({
    ...createSeedData(),
    sessions: ctx.token !== null && keep ? { [ctx.token]: keep } : {},
    audit: appendAudit([], { actor: toActorRef(actor), action: "demo_reset" }),
  });
}

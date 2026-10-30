import type { z } from "zod";
import { ApiError } from "@/types/api";

/**
 * Re-validates input at the (mock) server boundary. The browser already ran
 * the same schemas for good error messages; this is the check that does not
 * trust the browser. Any failure is the stable code `validation`.
 */
export function parseInput<Schema extends z.ZodType>(schema: Schema, input: unknown): z.output<Schema> {
  const result = schema.safeParse(input);
  if (!result.success) throw new ApiError("validation");
  return result.data;
}

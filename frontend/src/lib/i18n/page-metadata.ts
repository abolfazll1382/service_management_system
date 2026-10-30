import type { Metadata } from "next";
import { getServerT } from "./server";
import type { TranslationKey } from "./types";

/** `export const generateMetadata = () => titleFor("catalog.list.title")` — a per-page, localized <title>. */
export async function titleFor(key: TranslationKey): Promise<Metadata> {
  const t = await getServerT();
  return { title: t(key) };
}

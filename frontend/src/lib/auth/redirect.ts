/**
 * Where to go after signing in. The `next` value comes from the URL, so it
 * is attacker-controllable: only same-site paths are honoured.
 *
 * Rather than pattern-match the known tricks ("//evil.example", "/\evil.example",
 * a tab or newline slipped between the slashes — browsers strip those and read
 * the result as protocol-relative), the value is parsed with the same URL
 * parser browsers use and accepted only if it still points at this site.
 */
const PLACEHOLDER_ORIGIN = "http://portal.invalid";

export function safeNextPath(next: string | null | undefined, fallback: string): string {
  if (!next || !next.startsWith("/")) return fallback;
  try {
    const resolved = new URL(next, PLACEHOLDER_ORIGIN);
    if (resolved.origin !== PLACEHOLDER_ORIGIN) return fallback;
    return `${resolved.pathname}${resolved.search}${resolved.hash}`;
  } catch {
    return fallback;
  }
}

export function loginUrl(loginPath: string, returnTo: string): string {
  return `${loginPath}?next=${encodeURIComponent(returnTo)}`;
}

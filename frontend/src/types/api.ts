import type { PublicUser } from "./user";

/**
 * Errors cross the API boundary as stable CODES, never as English sentences,
 * so the UI can render them in whichever language is active (see the
 * `errors.*` keys in the dictionaries). A real backend would map HTTP status
 * and a machine-readable error field onto these same codes.
 */
export const API_ERROR_CODES = [
  "unauthenticated",
  "forbidden",
  "not_found",
  "validation",
  "invalid_credentials",
  "national_id_taken",
  "phone_taken",
  "username_taken",
  "service_unavailable",
  "invalid_transition",
  "request_closed",
  "network",
] as const;
export type ApiErrorCode = (typeof API_ERROR_CODES)[number];

export class ApiError extends Error {
  readonly code: ApiErrorCode;

  constructor(code: ApiErrorCode) {
    super(code);
    this.name = "ApiError";
    this.code = code;
  }
}


/** What a successful register/login returns: the bearer token and who it belongs to. */
export interface AuthResult {
  token: string;
  user: PublicUser;
}

export interface Paged<T> {
  items: T[];
  total: number;
  /** 1-based. */
  page: number;
  pageSize: number;
}

# Citizen Services API

Django 5.2 + Django REST Framework + PostgreSQL 16 backend for the **National Citizen Services Portal**
demo frontend (Next.js). Customers file service requests (loans, raw materials, vehicles, housing), staff
process them inside their departments, administrators run everything.

> **This is a demonstration system.** It is not affiliated with, endorsed by, or connected to any government
> body or real service. It does not integrate with any national identity, SMS or e-government service, and
> it does not issue official documents. Names, national IDs and phone numbers in the seed data are invented.
> Treat anything real users type into it as personal data (see [Security notes](#security-notes)).

- [Quick start (Docker)](#quick-start-docker) · [Local development](#local-development) · [Demo accounts](#demo-accounts)
- [Connecting the frontend](#connecting-the-frontend) · [API reference](#api-reference) · [Error contract](#error-contract)
- [Architecture](#architecture) · [Business rules](#business-rules) · [Configuration](#configuration)
- [Management commands](#management-commands) · [Quality](#quality-tests-linting-types) · [Security notes](#security-notes)
- [Going beyond the demo](#going-beyond-the-demo) · [Where it differs from the frontend's mock](#where-it-differs-from-the-frontends-mock)

## Quick start (Docker)

```bash
docker compose up --build        # PostgreSQL 16 + the API; first start migrates and seeds the demo data
```

| What | Where |
|---|---|
| API | <http://localhost:8000/api/> |
| Interactive docs (Swagger UI, loaded from a CDN, so the browser needs internet) | <http://localhost:8000/api/docs/> |
| OpenAPI 3 document | <http://localhost:8000/api/schema/> |
| Liveness + database check | <http://localhost:8000/health/> |
| PostgreSQL (this machine only) | `127.0.0.1:5432`, user / password / database `portal` |

Both ports are bound to `127.0.0.1` on purpose: the demo accounts share a public password and the stack
exposes a "reset everything" endpoint. Try it:

```bash
curl -s localhost:8000/api/auth/login/staff/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"reza","password":"Demo@1234"}'
# → {"token":"…","user":{"id":"…","role":"staff","username":"reza", …}}

curl -s localhost:8000/api/requests/queue/ -H "Authorization: Bearer <token>"
```

`docker compose down` stops it (the database lives in the `pgdata` volume; add `-v` to wipe it).
The compose file is a **demo configuration** — see [Going beyond the demo](#going-beyond-the-demo).

## Local development

Needs Python ≥ 3.12 and a PostgreSQL 16 server (`make db` starts one in Docker with the credentials
`config.settings.local` expects).

```bash
make install     # virtualenv + runtime and development dependencies
make db          # PostgreSQL 16 on 127.0.0.1:5432 (skip if you have your own; set DATABASE_URL)
make seed        # migrate, load the catalogue, create the demo accounts and requests
make run         # http://localhost:8000  (config.settings.local: DEBUG on, docs and demo reset on)
make check       # lint + strict types + migrations in sync + valid OpenAPI + the whole test-suite
make help        # every target
```

## Demo accounts

`seed_demo_data` creates these. **All of them use the password `Demo@1234`, which is public** (it is in this
file and on the frontend's login pages). Never seed a deployment that holds real data.

| Role | Sign in with | Scope |
|---|---|---|
| Administrator | username `admin` | everything |
| Staff — loans | username `reza` | department `loan` |
| Staff — raw materials | username `sara` | `raw_material` |
| Staff — vehicles | username `ali` | `vehicle` |
| Staff — housing | username `maryam` | `housing` |
| Customer Amir | national ID `0045813922` | own requests |
| Customer Maryam | national ID `1277348561` | own requests |
| Customer Hossein | national ID `0592846717` | own requests |

Eight requests in every state of the workflow are seeded as well (one of them has an *internal note* — log in
as a customer and check that it never appears). `POST /api/demo/reset/` (administrators; only where
`ENABLE_DEMO_RESET=true`) restores all of this.

## Connecting the frontend

The frontend talks to its backend through the modules in `src/lib/api/` (today they call an in-memory mock).
Swapping them for real HTTP calls does not touch hooks or components. The endpoints were designed to match
those modules one to one:

| Frontend call | HTTP |
|---|---|
| `authApi.register(input)` | `POST /api/auth/register/` |
| `authApi.loginCustomer(input)` | `POST /api/auth/login/customer/` |
| `authApi.loginStaff(input)` | `POST /api/auth/login/staff/` |
| `authApi.logout()` | `POST /api/auth/logout/` → 204 |
| `authApi.me()` | `GET /api/auth/me/` |
| `catalogApi.listServices()` / `getService(id)` | `GET /api/catalog/services/` · `GET /api/catalog/services/<id>/` |
| `catalogApi.setServiceActive(id, isActive)` | `PATCH /api/catalog/services/<id>/active/` `{"isActive": bool}` |
| `requestsApi.create(input)` | `POST /api/requests/` |
| `requestsApi.listMine()` | `GET /api/requests/mine/` (a plain array) |
| `requestsApi.queue(query)` | `GET /api/requests/queue/?status=&departmentId=&assignment=mine\|unassigned&search=&page=&pageSize=` |
| `requestsApi.get(id)` | `GET /api/requests/<id>/` |
| `requestsApi.transition(id, input)` | `POST /api/requests/<id>/transition/` `{"status", "note"?}` |
| `requestsApi.assign(id, assigneeId)` | `POST /api/requests/<id>/assign/` `{"assigneeId": id\|null}` |
| `requestsApi.assignableStaff(dept)` | `GET /api/requests/assignable-staff/?departmentId=` |
| `requestsApi.addMessage(id, input)` | `POST /api/requests/<id>/messages/` `{"visibility", "body"}` → 201 |
| `staffApi.list()` / `create(input)` / `update(id, input)` | `GET /api/staff/` · `POST /api/staff/` · `PATCH /api/staff/<id>/` |
| `auditApi.list(query)` | `GET /api/audit/?page=&pageSize=` |
| `demoApi.reset()` | `POST /api/demo/reset/` → 204 |

All bodies and responses are JSON in the frontend's own shapes (camelCase, ISO-8601 UTC timestamps with
milliseconds). Authentication is `Authorization: Bearer <token>`; send `Accept-Language: fa` or `en` to get
error `detail` text in that language. A minimal replacement for `mockRequest` (set
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`; CORS for `http://localhost:3000` is already allowed):

```ts
// src/lib/api/httpClient.ts — sketch
import { ApiError, type ApiErrorCode } from "@/types/api";
import { useSessionStore } from "@/lib/auth/sessionStore";

export async function http<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = useSessionStore.getState().token; // read when the call is MADE, as the mock does
  let response: Response;
  try {
    response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}${path}`, {
      method,
      headers: {
        ...(body !== undefined && { "Content-Type": "application/json" }),
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("network"); // the server could not be reached at all
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError((data?.code ?? "network") as ApiErrorCode);
  return data as T;
}
```

The backend returns two validation message keys the frontend dictionary does not have yet
(`validation.invalid`, `validation.password.max`) — see the [deviations](#where-it-differs-from-the-frontends-mock).

## API reference

The authoritative, always-current reference is the generated OpenAPI document (`/api/docs/`, or
`make schema` → `schema.yml`). Summary:

| Endpoint | Who | Notes |
|---|---|---|
| `POST /api/auth/register/` | public | Creates a customer and signs them in → `{token, user}`. 409 `national_id_taken` / `phone_taken`. Rate limited. |
| `POST /api/auth/login/customer/` | public | National ID (Persian/Arabic digits accepted) + password. Rate limited. |
| `POST /api/auth/login/staff/` | public | Username + password; administrators sign in here too. Rate limited. |
| `POST /api/auth/logout/` | anyone | Revokes the presented token. Idempotent: always 204, even for a dead or missing one. |
| `GET /api/auth/me/` | signed in | The account behind the token. |
| `GET /api/catalog/services/`, `/<id>/` | public | Services with their dynamic form `fields` and `isActive`. |
| `PATCH /api/catalog/services/<id>/active/` | admin | Pause / resume a service (audited). |
| `POST /api/requests/` | customer | Files a request; `details` is validated against the service's `fields`. |
| `GET /api/requests/mine/` | customer | The caller's requests, newest activity first (not paginated). |
| `GET /api/requests/queue/` | staff, admin | Paged queue limited to the caller's departments → `{items,total,page,pageSize,counts}`. |
| `GET /api/requests/<id>/` | owner, staff of the department, admin | Internal notes only for staff/admin. |
| `POST /api/requests/<id>/transition/` | staff of the department, admin | Status change along the workflow. |
| `POST /api/requests/<id>/assign/` | staff of the department, admin | Staff: claim for themselves or release. Admin: assign to any eligible staff member (active, in that department) or release. |
| `GET /api/requests/assignable-staff/` | staff, admin | Active staff of a department. |
| `POST /api/requests/<id>/messages/` | owner (public only), staff, admin | Public message or internal note. |
| `GET/POST /api/staff/`, `PATCH /api/staff/<id>/` | admin | Team management; deactivation ends sessions at once. |
| `GET /api/audit/` | admin | Newest first. |
| `POST /api/demo/reset/` | admin | Only when `ENABLE_DEMO_RESET=true`; otherwise it does not exist (404). |
| `GET /health/` | public | `{"status":"ok"}`, or 503 when PostgreSQL is unreachable. Outside `/api`, exempt from the HTTPS redirect. |

Every response carries an `X-Request-ID` (a safe caller-supplied one is kept) that also appears in the logs.

## Error contract

Every failure — including 404s, 405s, parse errors and unexpected 500s — has the same JSON body:

```json
{ "code": "validation", "detail": "…human text in the Accept-Language language…",
  "errors": { "nationalId": ["validation.nationalId.checksum"], "details.amount": ["validation.number.min"] } }
```

`errors` maps a field (nested ones as `details.<key>`; `non_field_errors` for the body as a whole) to
*dictionary keys* of the frontend's `validation.*` messages — never to English sentences.

| `code` | HTTP | When |
|---|---|---|
| `unauthenticated` | 401 | Missing, malformed, expired or revoked token; deactivated account. |
| `invalid_credentials` | 401 | Wrong username / national ID / password (one message for all causes). |
| `forbidden` | 403 | Signed in but not allowed (wrong role, other department). |
| `not_found` | 404 (405 for a wrong verb) | Unknown route or id. A customer asking for someone else's request gets this too. |
| `validation` | 400 (413 oversized body, 415/406/… for content-type issues) | Bad input. |
| `national_id_taken`, `phone_taken`, `username_taken` | 409 | Uniqueness conflicts (also when two requests race). |
| `service_unavailable` | 409 | The service is paused. |
| `invalid_transition` | 409 | Not a legal move from the current status. |
| `request_closed` | 409 | The request is `closed` (terminal). |
| `network` | 429 / 5xx | Throttled (with `Retry-After`) or an unexpected server error — retry later. |

## Architecture

```
config/settings/{base,local,production,test}.py   12-factor settings (django-environ); production refuses weak/missing secrets
apps/
  core/      error contract, request-id & body-limit middleware, strict JSON parser, Persian utilities
             (national-ID check digit, digit normalisation), pagination, OpenAPI hooks, demo seeding/reset
  users/     User (customer | staff | admin in one table), AccessToken, authentication, policies, services, selectors
  catalog/   Service + dynamic field definitions, server-side validation of a request's `details`
  requests/  ServiceRequest, TimelineEvent, the workflow state machine, services, selectors
  audit/     AuditLog + service
tests/       pytest-django against real PostgreSQL
```

Conventions (HackSoft style): **models** hold schema, constraints and indexes only; **services**
(`services.py`) perform every mutation inside `transaction.atomic`; **selectors** (`selectors.py`) are pure
reads; **serializers** are split into write (validation → dictionary keys) and read (output shape); **views**
are thin class-based `APIView`s: authenticate → coarse permission → validate → one service/selector call → render.

Design decisions worth knowing:

- **One policy, two layers.** `apps.users.policies.can(actor, Action, resource)` is a pure function. DRF
  permission classes (`allows(Action.X)`) are the coarse door; the services re-check object by object
  (department confinement, ownership) using the same function. Nothing is decided in a view.
- **Missing vs forbidden.** A customer cannot tell "someone else's request" from "no such request" (both
  `not_found`); staff get `forbidden` for another department's request, as the frontend contract specifies.
- **Opaque tokens, not JWTs.** Sign-in issues 32 random bytes; only their SHA-256 is stored, with an expiry
  (8 h) and `revoked_at`. Logging out, deactivating an account, or resetting the demo takes effect on the
  next request — impossible with stateless JWTs.
- **Concurrency.** Mutations lock rows in one global order (users by id → service → request) with
  `SELECT … FOR UPDATE`; permissions are re-decided on the *locked* actor so a just-revoked right cannot be
  used; timeline `sequence` numbers are allocated under the request lock; unique-index races are turned
  into the same domain errors the pre-checks raise. `tests/test_concurrency.py` exercises this with real
  threads and connections.
- **The database enforces invariants too**: CHECK constraints for role-shaped rows, status/assignee
  consistency and length limits, UNIQUE national ID / phone / username / tracking code, composite indexes
  for the queue, a trigram index for search. `tests/test_db_constraints.py` proves bad rows are refused
  even if the application is bypassed.
- **Passwords**: Argon2id (19 MiB, t=2, p=1); a decoy hash makes "unknown user" cost the same as "wrong password".
- **Audit trail**: every sign-in, failed sign-in, request creation / status change / assignment / message,
  team change, service pause and demo reset is recorded with a snapshot of who did it.

## Business rules

- **Roles.** *Customer*: registers and signs in with national ID (10 digits, mod-11 check digit, repeated digits
  rejected) + password; files requests; sees only their own; may post **public** messages on them.
  *Staff*: signs in with a username; confined to their `departmentIds`; reads the queue, changes status, claims
  or is assigned requests, posts public messages and **internal notes**; cannot file requests, manage the team,
  toggle services, read the audit trail or reset the demo. *Admin*: all of that across departments, plus team
  management, service availability, audit and demo reset; cannot file requests.
- **Workflow.** `pending_review → in_progress | rejected` · `in_progress → needs_correction | approved | rejected` ·
  `needs_correction → in_progress | rejected` · `approved → closed` · `rejected → closed` · `closed` is terminal.
  A note is required for `rejected` and `needs_correction`.
- **Side effects.** A staff member moving an unassigned request to `in_progress` claims it. A customer's public
  message on a `needs_correction` request moves it back to `in_progress` (recorded as the customer's action).
  Internal notes are removed server-side from everything a customer can receive.
- **Deactivating staff** revokes their tokens immediately and releases their open requests (closed history keeps
  its assignee).
- **Dynamic catalogue.** Each service lists its own extra form fields (`text` | `number` | `select`); the same
  definition drives the frontend's form and the backend's validation of `details`. Unknown keys are dropped.
- **Persian input.** Persian and Arabic-Indic digits are normalised before validation and search
  (national ID, phone `09xxxxxxxxx`, postal code, tracking codes, search text).

## Configuration

Settings come from environment variables; a `.env` file next to `manage.py` is read when present (copy
`.env.example`). Real environment variables always win. `manage.py` defaults to `config.settings.local`,
gunicorn (and the Docker image) to `config.settings.production`.

| Variable | Default | Meaning |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(required in production)* | ≥ 50 random characters; production refuses `django-insecure…` and short values. |
| `DJANGO_ALLOWED_HOSTS` | *(required in production)* | Comma-separated host names. `127.0.0.1`/`localhost` are always added for health checks. |
| `DATABASE_URL` | *(required)* | `postgres://user:pass@host:5432/db`. |
| `DB_CONN_MAX_AGE` | `60` | Seconds a connection is reused. |
| `DB_STATEMENT_TIMEOUT_MS` | `30000` | Per-statement timeout (0 = none). |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Frontend origins; no wildcard. |
| `DJANGO_BEHIND_PROXY` | `true` | Trust `X-Forwarded-Proto` (only behind a proxy that overwrites it). |
| `DJANGO_SECURE_SSL_REDIRECT` | `true` | Redirect HTTP → HTTPS (`/health/` exempt). |
| `DJANGO_SECURE_HSTS_SECONDS` | `31536000` | HSTS max-age (`0` disables). |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | `true` | |
| `DJANGO_SECURE_HSTS_PRELOAD` | `false` | Opt-in; requires ≥ 1 year and subdomains. |
| `ACCESS_TOKEN_TTL_SECONDS` | `28800` | Lifetime of a sign-in. |
| `THROTTLE_AUTH_LOGIN` | `20/min` | Sign-in attempts per client address. |
| `THROTTLE_AUTH_REGISTER` | `10/min` | Registrations per client address. |
| `NUM_PROXIES` | `0` | Reverse proxies in front of the app; `0` ignores `X-Forwarded-For`. |
| `CACHE_URL` | `locmemcache://portal-throttle` | Throttle counters; use a shared cache with several workers/replicas. |
| `API_MAX_BODY_BYTES` | `65536` | Larger bodies are refused with 413 before being read. |
| `ARGON2_TIME_COST` | `2` | Argon2id parameters. |
| `ARGON2_MEMORY_COST_KIB` | `19456` | |
| `ARGON2_PARALLELISM` | `1` | |
| `ENABLE_DEMO_RESET` | `false` (`true` in local) | `POST /api/demo/reset/` — wipes data. |
| `ENABLE_API_DOCS` | `false` (`true` in local) | `/api/schema/` and `/api/docs/`. |
| `LOG_LEVEL` | `INFO` | Application log level (logs go to stdout with the request id). |
| `RUN_MIGRATIONS` | `true` | Entrypoint: apply migrations (under an advisory lock). |
| `SYNC_CATALOG` | `true` | Entrypoint: load/refresh the built-in service catalogue. |
| `SEED_DEMO_DATA` | `false` (`true` in the compose file) | Entrypoint: create demo accounts that share a **public** password. |
| `DB_WAIT_TIMEOUT` | `60` | Entrypoint: seconds to wait for PostgreSQL. |
| `WEB_CONCURRENCY` | `min(2×CPU+1, 9)` | Gunicorn worker processes. |
| `GUNICORN_THREADS` | `2` | Threads per worker (each holds its own DB connection). |
| `GUNICORN_BIND` | `0.0.0.0:8000` | |
| `GUNICORN_TIMEOUT` | `45` | Seconds before a stuck worker is killed. |
| `GUNICORN_GRACEFUL_TIMEOUT` | `30` | |
| `GUNICORN_KEEPALIVE` | `5` | |
| `GUNICORN_MAX_REQUESTS` | `2000` | Recycle a worker after this many requests (with jitter). |
| `GUNICORN_MAX_REQUESTS_JITTER` | `200` | |
| `GUNICORN_LOG_LEVEL` | `info` | |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Peers allowed to set `X-Forwarded-*`; list your proxy's address. |
| `BOOTSTRAP_ADMIN_PASSWORD` | *(unset)* | Read by `bootstrap_admin` instead of prompting. |

## Management commands

| Command | Purpose |
|---|---|
| `migrate_locked` | `migrate` under a PostgreSQL advisory lock — replicas that start together take turns. |
| `wait_for_db [--timeout 60]` | Block until PostgreSQL accepts connections. |
| `sync_catalog` | Load/refresh the built-in services (keeps each availability switch). |
| `seed_demo_data [--reset [--no-input]]` | Create missing demo data; `--reset` restores the seed (asks first). Refuses to run where `ENABLE_DEMO_RESET` is false. |
| `bootstrap_admin --username U --name-fa … --name-en …` | Create the first administrator. The password is read from `BOOTSTRAP_ADMIN_PASSWORD` or prompted for twice — never accepted as an argument. |
| `purge_access_tokens [--older-than-days 7]` | Delete tokens that expired or were revoked more than N days ago (never a live one). Run it daily (cron / Kubernetes CronJob). |

## Quality: tests, linting, types

```bash
make check      # ruff + ruff format --check + mypy --strict (django-stubs) + makemigrations --check
                # + OpenAPI validation (zero warnings) + the full pytest suite
make test-fast  # skip the multi-connection concurrency tests
```

More than 700 tests run against a real PostgreSQL 16 (no SQLite, no mocks of the database):

- a faithful port of the frontend's own test-suite (auth, RBAC, workflow, admin, policies, Persian utilities,
  validation, catalogue, seed data) so both ends are held to the same rules;
- server-only concerns: token storage / expiry / revocation, throttling (including `X-Forwarded-For`
  spoofing), request ids, CORS, body limits, malformed JSON, the error contract for *every* failure path,
  database constraints and indexes, real multi-thread concurrency, Argon2, the OpenAPI document,
  management commands, production settings and `check --deploy` (each in a fresh interpreter), and the
  deployment files themselves (entrypoint, Dockerfile, compose, `.env.example` and this README must mention
  every environment variable the code reads).

## Security notes

Implemented: opaque hashed tokens with expiry and revocation; Argon2id; unknown-user timing equalisation;
per-address throttling of sign-in and registration; deny-by-default permissions with object-level checks;
server-side stripping of internal notes; strict JSON (types, NaN/Infinity, nesting depth, NUL/surrogates),
body-size ceiling; no stack traces or SQL in any response; production settings that fail closed; HTTPS
redirect + HSTS; a non-root, capability-dropped container; secrets only from the environment.

Not done (deliberately out of scope for a demo — pick these up before real use):

- **Personal data.** National IDs and phone numbers are stored in clear text. For real use: field-level
  encryption or pseudonymisation, a retention/deletion policy, access logging for staff reads, and a legal
  basis for processing. Phone numbers are not verified (no SMS/OTP).
- **Audit trail immutability.** Rows are append-only *by convention* (no code path edits them, and
  `demo/reset` clears them). Enforce it in the database (revoked `UPDATE`/`DELETE`, a trigger, or an
  append-only role) and ship the log to an external store.
- **Throttling** is per client address with per-process counters by default; use a shared cache
  (`CACHE_URL`) and add account-level lock-out / CAPTCHA / MFA for staff and administrator accounts.
- **Operations.** No metrics endpoint, tracing, structured (JSON) logs, backups or secret rotation are included.
- **Browser side.** Bearer tokens are readable by any script on the frontend's origin; keep the token
  lifetime short, ship a strict Content-Security-Policy with the frontend, or move to HTTP-only cookies
  (which then need CSRF protection).
- **No penetration test** has been performed.

## Going beyond the demo

`docker-compose.yml` is a demo. For anything else:

1. Use a managed PostgreSQL 16 (the `pg_trgm` extension is created by a migration; on PostgreSQL ≥ 13 the
   database owner may do so). Budget connections: `WEB_CONCURRENCY × GUNICORN_THREADS × replicas`.
2. Put the API behind a TLS-terminating proxy that **overwrites** `X-Forwarded-Proto` / `X-Forwarded-For`; set
   `FORWARDED_ALLOW_IPS` to the proxy's address and `NUM_PROXIES` to the number of proxies.
3. Set a real `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS`. Keep `ENABLE_DEMO_RESET`,
   `ENABLE_API_DOCS` and `SEED_DEMO_DATA` **off**.
4. Create the first administrator with `bootstrap_admin`; change nothing else by hand.
5. Several replicas: migrations are safe to start in parallel (`migrate_locked`), or run them once as a job with
   `RUN_MIGRATIONS=false` on the web pods. Point `CACHE_URL` at a shared cache so throttling is exact
   (`redis://…` needs `pip install redis`; `dbcache://portal_throttle` needs `manage.py createcachetable`).
6. Schedule `purge_access_tokens` daily; collect stdout logs (every line carries the request id); alert on
   `/health/`.
7. Work through [Security notes](#security-notes).

## Where it differs from the frontend's mock

The backend follows the frontend's contract; these are the deliberate differences:

- **Sign-in accepts Persian/Arabic-Indic digits** in the national ID (the mock rejected them); all inputs are
  normalised first.
- **Length limits count Unicode code points**, not UTF-16 units (matters only for emoji and similar).
- **Backend-only validation keys**: `validation.invalid` (generic "invalid value", e.g. wrong JSON type or an
  unknown enum value) and `validation.password.max`. Add them to the frontend dictionaries (both languages), or
  the UI will show the raw key.
- **A failed staff sign-in** whose "username" is not username-shaped is audited with the target `(invalid)`
  instead of echoing arbitrary text into the audit trail.
- **`GET /api/requests/mine/` is not paginated** (it returns a plain array, as the frontend expects); a very
  active customer's list grows without bound — add paging before real use.
- **`POST …/messages/` answers 201** (it creates a message); the body is the updated request, as for the other
  mutations.
- **List problems in `departmentIds`** are reported under `departmentIds`, not `departmentIds.<n>`.
- HTTP statuses accompany every error `code` (the mock had none); a wrong HTTP verb answers 405 with code
  `not_found`; bodies over the size limit answer 413.

## Troubleshooting

- *`ImproperlyConfigured: DJANGO_SECRET_KEY …` at start* — production needs a real secret and allowed hosts (see above).
- *`could not connect to server`* — check `DATABASE_URL`; `make db` starts a matching PostgreSQL.
- *401 right after signing in* — tokens live for `ACCESS_TOKEN_TTL_SECONDS`; they also die when the account is
  deactivated or the demo is reset.
- *429 `network` while testing* — you hit the sign-in throttle; wait for `Retry-After` seconds or raise `THROTTLE_AUTH_LOGIN`.
- *Browser blocks calls from the frontend* — add its origin to `CORS_ALLOWED_ORIGINS`.
- *Swagger UI is blank* — it loads its assets from jsDelivr; the machine viewing it needs internet access.

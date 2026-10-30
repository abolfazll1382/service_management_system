# National Citizen Services Portal · سامانه جامع خدمات شهروندی

A frontend-only demonstration of a **service registration and request-handling system**, built as a portfolio project: a public site where citizens register and apply for services, and a staff console where each team member works only the departments they are responsible for. The whole interface switches between **Persian (RTL)** and **English (LTR)** with one button.

> **This is a demonstration.** It is not affiliated with, and does not imitate, any real government body or service. There are no official emblems, no "verified" badges, no legal notices and no printable official documents. Everything runs in your browser; data is stored in `localStorage`, and no request is ever sent anywhere.

Built with Next.js 16 (App Router) · React 19 · TypeScript (strict) · Tailwind CSS v4 · React Hook Form + Zod · Zustand · Vitest.

---

## What's in it

**Customer site** (`/`)

- Browse services grouped by department (loans, raw materials, vehicles, housing), with requirements and typical processing time.
- Register once (full name, National ID with checksum validation, mobile number, postal code, address, password), then sign in.
- A three-step **apply wizard** (your details → the service's own questions → review and confirm) ending in an on-screen confirmation with a **tracking code**.
- **My requests**: status, full activity timeline, and a reply box. Staff can ask for a correction; replying moves the request back into review automatically.

**Staff console** (`/console`)

- A **request queue** limited to the departments the signed-in person is assigned to, with status tabs and live counts, search (tracking code, name, National ID, phone — Persian digits work), "assigned to me", and paging.
- A **work panel** per request: applicant details and answers, change status (only legal next steps are offered; a rejection or a correction request must include a note the applicant will read), claim or assign, and post either a public reply or an internal staff-only note.
- **Administrators** additionally get: **Team** (create staff, choose their departments, deactivate), **Services** (pause or resume each service), **Audit log**, and a **Reset demo data** button.

**Both languages, fully**: Persian and English dictionaries are type-checked against each other, dates are Jalali in Persian and Gregorian in English, digits follow the language, and the layout mirrors.

---

## Quick start

Requires Node.js 20.9 or newer (developed on Node 22).

```bash
npm install
npm run dev          # http://localhost:3000
```

| Script              | What it does                                        |
| ------------------- | --------------------------------------------------- |
| `npm run dev`       | Development server                                  |
| `npm run build`     | Production build                                    |
| `npm start`         | Serve the production build                          |
| `npm run typecheck` | `tsc --noEmit` (strict)                             |
| `npm run lint`      | ESLint, including the architecture boundary rules   |
| `npm test`          | Vitest unit and API-level tests                     |
| `npm run check`     | typecheck + lint + tests                            |

Set `NEXT_PUBLIC_MOCK_FAILURE_RATE=0.3` (for example in `.env.local`) to make 30 % of calls fail with a network error, which is a quick way to see every loading, error and retry state.

---

## Demo accounts

Every account uses the password **`Demo@1234`**. The sign-in pages list them and fill the form for you.

**Customers** (sign in at `/login` with the National ID)

| Name           | National ID  |
| -------------- | ------------ |
| امیر حسینی      | `0045813922` |
| مریم احمدی      | `1277348561` |
| Hossein Karimi | `0592846717` |

(One seeded customer has a Latin-script name on purpose: people type their names in either script, and it keeps the right-to-left layout honest about mixed text.)

**Staff** (sign in at `/console/login` with the username)

| Username | Role          | Departments                     |
| -------- | ------------- | ------------------------------- |
| `admin`  | Administrator | all, plus team / services / audit |
| `reza`   | Staff         | Loans & Financing               |
| `sara`   | Staff         | Raw Materials                   |
| `ali`    | Staff         | Vehicles                        |
| `maryam` | Staff         | Housing                         |

The seed also contains eight requests (two per department) in different states. You can register a new customer with **Fill sample details** on the registration page, which generates a checksum-valid National ID.

### A three-minute tour

1. Open `/services`, pick **Personal loan**, choose **Register to apply**, fill sample details, and submit the request. Note the tracking code.
2. Sign out, open `/console/login`, sign in as `reza`. The new request is in his queue; open it, start the review (it is claimed for him), add an **internal note** and a **public reply**, then ask for a correction.
3. Sign in as `ali`. The loan request is not in his queue at all.
4. Back as the customer, open **My requests**: you see the public reply and the correction note, never the internal note. Reply, and the request returns to "In progress".
5. Sign in as `admin`: pause a service, add a staff member, read the audit log, press the language toggle anywhere.

---

## How permissions work

Three roles: **customer**, **staff**, **admin**. Departments are the unit of authorization: every request belongs to exactly one, and a staff member is granted a set of them.

| Action                                  | Customer    | Staff                       | Admin |
| --------------------------------------- | ----------- | --------------------------- | ----- |
| Submit a request                        | yes         | no                          | no    |
| Read a request / reply publicly         | own only    | own departments             | all   |
| Write an internal note, change status   | no          | own departments             | all   |
| Assign a request                        | no          | claim for self, own depts   | anyone eligible |
| Manage team, services, read audit log   | no          | no                          | yes   |

Rules worth knowing:

- All decisions go through one pure function, `can(actor, action, resource)` in `src/lib/auth/policies.ts`. Anything not explicitly allowed is denied. It is tested against the full matrix.
- **The mock server is the authority; the UI only hides things.** Identity comes from the session token alone (never from a field in the request). A customer asking for someone else's request gets *not found*; staff asking for another department's request get *forbidden*. Internal notes are stripped on the server for anyone who can't write them.
- The status workflow is data (`src/lib/domain/workflow.ts`): `pending_review → in_progress | rejected`, `in_progress → needs_correction | approved | rejected`, `needs_correction → in_progress | rejected`, `approved | rejected → closed`. The work panel offers only legal moves and the server rejects the rest. `closed` is final.
- Starting a review claims the request. A customer reply on a request that needs correction moves it back to *in progress*, recorded as the customer's action.
- Deactivating a staff member ends their sessions immediately and unassigns their open work. Admin accounts can't be edited from the UI, so nobody can lock the system out of its last administrator.
- The audit log records who did what, with identifiers only: never message text, never a full National ID (failed sign-ins keep a masked one such as `004•••••22`).

---

## Language and direction

- The language is a cookie (`portal-locale`), read on the server, so the very first byte already has the right `lang` and `dir`; no flash of the wrong language. Switching writes the cookie, flips `<html lang dir>` and refreshes the server components.
- Dictionaries live in `src/lib/i18n/dictionaries/{en,fa}`. English is the structural reference and Persian is typed against it, and `TranslationKey` is a compile-time union, so a missing, extra or misspelled key fails `tsc` rather than showing a blank label. A test also checks script purity (no stray Latin in Persian strings).
- Layout uses **logical properties** (`ms-`, `pe-`, `start-`, `text-start`, …) everywhere, and directional icons flip with `rtl:`. Codes, phone numbers and IDs are isolated with `<Ltr>` so the bidi algorithm can't reorder them; numeric inputs stay left-to-right inside a right-to-left form.
- Free text written by users (descriptions, messages) uses `dir="auto"` so punctuation lands on the correct side whichever script was typed.
- Dates and numbers come from `Intl` (`fa-IR` gives the Jalali calendar and Persian digits). Input accepts Persian, Arabic-Indic or Latin digits, with or without spaces or separators.
- Validation messages are rebuilt when the language changes, so an error on screen is re-translated in place without losing what was typed.

---

## Architecture

Code is organised in layers; each layer may import only from the layers to its left, never from those to its right. ESLint enforces it (`eslint.config.mjs`):

```
types → lib → providers / hooks → components/ui → components/domain → components/layout → features → app
```

```
src/
  app/            routes only: (site)/ customer pages, console/ staff pages, root layout, localized 404 and error pages, font, tokens
  features/       screens with behaviour: catalog, auth, apply (wizard), requests, console
  components/
    ui/           domain-free primitives (Button, Modal on native <dialog>, Table, FormField, Switch…)
    domain/       StatusBadge, TrackingCode, RequestTimeline, DetailList…
    layout/       site header/footer, ConsoleShell, route guards (RequireAuth, RequirePermission)
  providers/      Locale, Auth (session rehydration + cross-tab sync), Toast
  hooks/          useAsync, useSession/useCan, useDebouncedValue, …
  lib/
    api/          the seam: what the UI calls (authApi, requestsApi, staffApi, …)
    mock-server/  the fake backend: validation, authorization, workflow, audit
    store/        the fake database (persisted Zustand store) and the seed data
    auth/         policies (RBAC), password hashing (demo), session store, safe redirects
    domain/       the status state machine
    catalog/      departments and services as data
    i18n/ validation/ utils/ demo/
  types/          the domain model, shared by everything
tests/            Vitest: policies, workflow, API/RBAC, validation, i18n, Persian utilities
```

**The one rule that keeps the backend replaceable.** UI code reaches data only through `@/lib/api`. Only `lib/api` may import `lib/mock-server`, and only `lib/mock-server` may touch the stored "database". A lint rule makes any other import an error. To use a real backend, rewrite the modules in `src/lib/api/` to call `fetch` with the same method names, return types and error codes (`ApiError` carries a stable code, never an English sentence, so messages stay translatable). Components and hooks don't change.

**Services are data.** Each service in `src/lib/catalog/services.ts` declares its own extra questions (`text`, `number`, `select`). The wizard renders them, the Zod schema is built from them (in the browser and in the mock server), and staff and customer views display the answers, all from the same definition. Adding a service is one entry, no new component.

**State.** React Hook Form owns form values (one form across all wizard steps); Zustand holds the session token, the persisted mock database, and only the *navigation* of the wizard. Auth state is hydrated in an effect with a `hydrated` flag, so server and first client render agree and a signed-in person is never bounced to sign-in for a frame.

**Look.** Lapis-and-turquoise palette, hairline borders and no shadows, Vazirmatn (self-hosted through `next/font/local`), a generic eight-pointed-star mark that deliberately resembles no real emblem. Colour is never the only carrier of meaning, focus rings are visible, the modal is a native `<dialog>`, and reduced-motion is respected.

---

## Extending it

- **Add a service:** append an entry to `SERVICES` in `src/lib/catalog/services.ts` (title and text in both languages, `fields`, `departmentId`). Nothing else is required.
- **Add a department:** add its id to `DEPARTMENT_IDS` (`src/types/department.ts`), an entry in `src/lib/catalog/departments.ts`, an icon key if you need a new icon, and grant it to staff. The permission code never names a department.
- **Change who can do what:** edit `src/lib/auth/policies.ts` and its test.
- **Add a language:** extend `LOCALES` (`src/types/i18n.ts`) and the per-language settings in `src/lib/i18n/config.ts` (text direction and `Intl` locale tag), then add a dictionary typed as `Dictionary`. The compiler lists every key that is missing.

---

## Testing and what was verified

- `npm run check` runs strict type-checking, ESLint (React Hooks rules plus the layer-boundary rules) and the Vitest suite. The suite covers the permission matrix, the status workflow, the API against the mock server (cross-department denial, customer isolation, internal-note stripping, closed-request freezing, session death on deactivation and reset, no credential leakage), validation, the i18n dictionaries, Persian digit and National ID utilities, and open-redirect protection.
- The production build was served and driven in headless Chromium in **both languages**: language switching and persistence, registration with validation, the full wizard, tracking code, customer replies, the whole staff flow (claim, internal note, public reply, correction, search and filters), department isolation for every staff account, admin pages, paused services, route guards, and a 390 px mobile pass for horizontal overflow. No console errors or failed requests were observed.
- That browser walk-through was a throwaway script and is **not** included; adding Playwright specs would be the natural next step.

---

## Security notes: read before reusing any of this

This project demonstrates *interface and architecture*, not a secure system.

- The "backend" runs in the browser. Anyone can open DevTools and edit `localStorage`; a client-side check can never be a security boundary. A real backend must enforce every rule in `policies.ts` itself.
- Passwords are salted and hashed with SHA-256 in the browser only so the demo database holds no plaintext. A real system hashes on the server with argon2id or bcrypt and never exposes a hash to the client.
- Sessions are bearer tokens in `localStorage`. A real system should use `HttpOnly`, `Secure`, `SameSite` cookies (or short-lived tokens), CSRF protection, rate limiting and lockout on sign-in, real session invalidation, and server-side audit logging.
- National IDs and phone numbers are personal data. Don't enter real ones here, and design retention and masking before handling any.
- `npm audit` reports advisories only in the development-only lint chain (`eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces`). `npm audit --omit=dev` is clean, so nothing in the shipped app or its runtime dependencies is affected. There is no upstream fix for `braces` yet and the suggested one is a breaking downgrade, so it was left alone.
- `npm install` also prints `eslint@9 … is no longer supported`. ESLint 10 exists, but the plugins `eslint-config-next` relies on (`eslint-plugin-react`, `-jsx-a11y`, `-import`) only declare support up to ESLint 9, so upgrading today would make the install fail. It is a lint-time tool only; revisit when that chain supports 10.

## Known limitations

- Single browser profile: the "database" is that browser's `localStorage`, shared across its tabs but not across devices.
- No file uploads, notifications, or password reset: the point was the request and permission workflow.
- The Persian dates are formatted, not edited: there is no Jalali date picker because no form needs one yet.
- Requires a modern browser (native `<dialog>`, `:has()`, logical CSS properties).

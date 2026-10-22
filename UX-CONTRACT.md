# UX contract

## Product context

- **Audience:** NIDS administrators, analysts, and viewers.
- **Primary jobs:** Review persisted alerts and flow observations, filter and page through records, inspect evidence, acknowledge alerts when permitted, and sign in/out.
- **Target market(s):** Academic technical project; no specific consumer market is inferred.
- **Active locales:** English interface; browser locale and timezone for date display.
- **Language/content register:** Concise operational English. Domain terminology follows `docs/API.md`.
- **Timezone/calendar policy:** Send timezone-aware ISO-8601 values. Display dates in the browser timezone and retain exact source timestamp in the details view.
- **Accessibility target:** WCAG 2.2 AA.

## Business-context sources

| Domain / scope | Authoritative source | Source type | Reviewed date |
|---|---|---|---|
| Permissions, auth, routes, filters, stream | `docs/API.md`, `backend/app/api/auth.py`, `backend/app/api/routes.py`, `backend/app/api/websockets.py` | API and server authorization | 2026-10-22 |
| Persisted flow and alert fields | `backend/app/schemas.py`, `backend/app/database/models.py` | Data contract | 2026-10-22 |
| Product scope | `docs/IMPLEMENTATION_PLAN.md`, `docs/ARCHITECTURE.md` | Project plan and architecture | 2026-10-22 |

## Visual contract

- **Project `DESIGN.md`:** Root `DESIGN.md`.
- **Token ownership model:** Runtime CSS is canonical; `DESIGN.md` mirrors accepted values.
- **Runtime design-system/token source:** `frontend/src/styles.css` CSS variables.
- **Mapping/export/adapters:** Tailwind `@theme inline` aliases the CSS variables; components use CSS classes.
- **Token drift gate:** Update CSS and `DESIGN.md` together; inspect the diff and run `npm run typecheck` plus `npm run build`.
- **Supported themes:** Light only.
- **Design-context owner/review policy:** Product UI changes update this contract and `DESIGN.md` in the same change when behavior or shared tokens change.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Read-only tables and filters | Shared `DataTable`/`FilterBar` patterns in dashboard | API list endpoints and URL search params | Desktop table / narrow record cards | Component tests and browser review |
| Select/Listbox | Native `<select>` | Browser platform, API enum values | Native only | Keyboard review and narrow layout |
| Date | `datetime-local` inputs converted to ISO with timezone | API `since`/`until` | Native typed date/time | Filter round-trip and validation |
| Form | Shared login form | `/auth/token` and `UserCreate` constraints | Sign-in | Keyboard, validation and failure recovery |
| Scrollbar | Global CSS baseline in `frontend/src/styles.css` | CSS standard scrollbar properties with WebKit fallback | Global; no geometry variants | Desktop and narrow scroll surfaces |
| Toast | None; inline status/banner owner | N/A | Persistent inline feedback | Live region review |
| CRUD | Alert-row action, pessimistic update | `PATCH /alerts/{id}/acknowledge` | Single-record acknowledgement only | Role check, pending and failure state |
| Detail view | Inline expandable row | Alert/flow read schemas | Inline | Keyboard and narrow layout |

## Component behavior

| Component | Default | Hover | Focus | Active | Disabled | Busy | Error |
|---|---|---|---|---|---|---|---|
| Button | labeled, stable size | tonal shift | visible ring | brief pressed state | muted, no pointer | label retained, `aria-busy` | inline form/page message |
| Icon button | named with tooltip | tonal shift | visible ring | brief pressed state | muted | stable icon box | inline message |
| Input | visible label | border darkens | visible ring | n/a | native disabled | n/a | inline associated text |
| Secret input | masked | border darkens | visible ring | n/a | n/a | submit blocked | inline auth error |
| Filter select | current value | border darkens | visible ring | native popup | n/a | n/a | filter-level validation |
| Table/list | semantic, stable rows | row tint | links/actions focus normally | n/a | n/a | retain rows and show updating | retain data with retry banner |

## Dataset navigation

- **Admin tables:** No user-management table is included in Step 8; the API's admin-only create-user route remains available through API docs.
- **Exploratory lists:** Alerts and flows. Tables sort by API order: newest first, stable ID tie-break.
- **URL state:** Committed filters, page, and page size are query parameters. Credentials and tokens are never in the URL. Temporary filter draft values stay local until Apply.
- **Page size:** 25 by default; 50 and 100 available, within API limit.
- **Empty/loading/error:** Keep list frame stable; distinguish loading, first-use empty, filter no-results, and API failure. Failure offers retry; stale results are labeled.
- **Back/scroll restoration:** Browser back/forward restores URL filters and page. New filter application resets page to 1; out-of-range page is clamped after response.
- **Selection:** No row selection or bulk mutation. Alert acknowledgement is single-record and pessimistic; after success update that row and refetch current list.

## Flow ledger

| Operation | Trigger | Pending | Success destination | Success feedback | Failure recovery | Focus outcome | Source ref |
|---|---|---|---|---|---|---|---|
| Sign in | Submit credentials | Disable submit, preserve username, never persist password | Intended protected route | Dashboard appears | Inline credential/API message, keep form | Remains on submit button | `/auth/token`, `/auth/me` |
| Filter | Apply filter form | Keep current rows marked updating | Same route, page 1 | Updated results and count | Retain rows and offer retry | Focus stays on Apply | API list endpoints |
| Acknowledge | Alert action | Disable that row action only | Same alert list | Row status changes to acknowledged | Keep row new, inline retry feedback | Focus stays at action | `PATCH /alerts/{id}/acknowledge` |
| Expand details | View details | Immediate | Same route | Evidence/timestamps shown inline | Not applicable | Focus stays on disclosure | Detail schema |
| Logout | Header action | Disable while request settles | Login | Session cleared | Clear local session regardless of response | Focus username on arrival | `/auth/logout` |

## Navigation and responsive behavior

- **Route titles:** `Alerts · Network observatory`, `Flows · Network observatory`, and `Sign in · Network observatory`.
- **Route errors / 403:** Missing session returns to sign-in with a safe same-origin return path. A 403 keeps the page visible and explains that the account cannot perform that action.
- **Route-state:** Alerts and Flows are primary nav links; filters/pagination are query state.
- **Navigation transformation:** Fixed left rail on wide screens; compact horizontal nav above content on narrow screens.
- **Responsive tables:** Desktop semantic table; below 760px show equivalent record cards with all fields and actions.
- **Truncation:** IDs and endpoints may wrap; full exact values are available in detail expansion. Do not rely on hover for access.
- **Focus:** No sticky obstruction; route changes focus the page heading.

## Overlays and feedback

- No dialogs or drawers in Step 8. Expand detail inline.
- Persistent API/stream state is inline and announced politely; mutation failure is kept beside the action.
- No transient toast for critical or actionable feedback.

## Async and resilience

- **Mutations:** Pessimistic acknowledgement; duplicate submission blocked per alert.
- **Offline/read-stale/write:** Existing response can remain visible and is marked stale after a failed refresh; actions remain available only when online and permitted.
- **Retry/backoff:** User-triggered retry for REST failures. WebSocket uses bounded exponential reconnect; reconnect resumes from last received `(created_at, id)` cursor.
- **Session:** Access and rotated refresh tokens live in memory only; page reload requires sign-in. Refresh before access expiry and on REST 401/WS 4401. Failed refresh clears session and returns to sign-in.
- **Stale requests:** Abort superseded list requests. Only the active request may clear loading state.
- **Permission change:** Server authorization is authoritative. A 403 explains the role boundary and does not retry the mutation.

## Validation

- Login checks nonempty username/password client-side; server remains authoritative for authentication.
- Filter date values are converted from local datetime inputs to aware UTC ISO strings. Since-after-until is blocked inline before request.
- Do not store, log, announce, or render passwords or token contents. Login failure does not discard the typed username.

## Permission and clipboard

- Viewer acknowledgement action is disabled and paired with visible text explaining that analyst/admin permission is required. The API enforces role checks.
- No clipboard action in Step 8.

## Verification

- **Static commands:** `npm run typecheck`, `npm test`, `npm run build`, premium UI `audit_project.py --mode strict`.
- **Browser/device/theme:** Chromium/desktop and narrow phone width; light theme only.
- **Accessibility:** Keyboard through sign-in, nav, filters, rows, disclosure, and acknowledgement; inspect focus and reduced motion.
- **Sibling flow:** No prior frontend screens; alerts and flows establish the shared list pattern.
- **Evidence:** Results are recorded in `docs/PROGRESS.md`; no test data is shown as production telemetry.

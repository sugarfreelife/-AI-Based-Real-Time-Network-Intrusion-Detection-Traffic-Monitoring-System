# UX contract

## Product context

- **Audience:** NIDS administrators, analysts, and viewers.
- **Primary jobs:** Review persisted activity totals, compare traffic and alert trends, inspect capture history and model/evaluation evidence, filter and page through flows and alerts, inspect evidence, acknowledge alerts when permitted, and sign in/out.
- **Target market(s):** Academic technical project; no specific consumer market is inferred.
- **Active locales:** English interface; browser locale and timezone for date display.
- **Language/content register:** Concise operational English. Domain terminology follows `docs/API.md`.
- **Timezone/calendar policy:** Send timezone-aware ISO-8601 values. Display dates in the browser timezone and retain exact source timestamp in the details view.
- **Accessibility target:** WCAG 2.2 AA.

## Business-context sources

| Domain / scope | Authoritative source | Source type | Reviewed date |
|---|---|---|---|
| Permissions, auth, routes, filters, stream | `docs/API.md`, `backend/app/api/auth.py`, `backend/app/api/routes.py`, `backend/app/api/websockets.py` | API and server authorization | 2026-10-23 |
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
| Overview analytics | `OverviewPage` with `TrafficTimelineChart` | `/analytics/summary` and `/analytics/timeline` | Hourly / daily buckets; UTC API values / browser-local labels | Range round-trip, empty data, responsive chart and accessible value table |
| Synthetic simulation | `SimulationPage` and authenticated `POST /simulation` | Real packet parser, flow builder, inference status and rule detector; no DB write | Fixed, bounded SYN burst on documentation IPs; explicitly synthetic | Auth required, rule evidence displayed, no persistence, reduced-motion support |
| Model status and evaluation | `ModelPage` | `/model/status`, configured trusted artifact, matching evaluation report | Explicit unavailable states; verified report only | No-model state, checksum/report mismatch, accessible per-class and confusion tables |
| User management | `UserManagementPage` | `/auth/users`, `/auth/users/{id}/status`; server-side admin role, audit trail, refresh-session revocation | Admin-only register and account create/status actions; desktop table / phone cards | Role denial, create validation, successful deactivation, pagination, own-account protection |
| Select/Listbox | Native `<select>` | Browser platform, API enum values | Native only | Keyboard review and narrow layout |
| Date | `datetime-local` inputs converted to ISO with timezone | API `since`/`until` | Native typed date/time | Filter round-trip and validation |
| Form | Login and user creation forms | `/auth/token` and `UserCreate` constraints | Sign-in; administrator creates analyst/viewer/admin accounts | Keyboard, validation and failure recovery |
| Scrollbar | Global CSS baseline in `frontend/src/styles.css` | CSS standard scrollbar properties with WebKit fallback | Global; no geometry variants | Desktop and narrow scroll surfaces |
| Toast | None; inline status/banner owner | N/A | Persistent inline feedback | Live region review |
| CRUD | Alert acknowledgement and admin user management | Alert acknowledgement and `/auth/users` status APIs | Single-record acknowledgement, account creation, or status change | Server role check, pending state, audit feedback, last-admin protection |
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

- **Admin tables:** The admin-only User management page lists and creates accounts and allows safe status changes. Server role checks remain authoritative; deactivation revokes refresh sessions.
- **Exploratory lists:** Capture history, alerts, and flows. Tables sort by API order: newest first, stable ID tie-break. Overview charts display persisted counts for the selected period.
- **URL state:** Committed filters, date range, timeline interval, page, and page size are query parameters. Credentials and tokens are never in the URL. Temporary filter draft values stay local until Apply.
- **Page size:** 25 by default; 50 and 100 available, within API limit.
- **Empty/loading/error:** Keep list frame stable; distinguish loading, first-use empty, filter no-results, and API failure. Failure offers retry; stale results are labeled.
- **Back/scroll restoration:** Browser back/forward restores URL filters and page. New filter application resets page to 1; out-of-range page is clamped after response.
- **Selection:** No row selection or bulk mutation. Alert acknowledgement is single-record and pessimistic; after success update that row and refetch current list.

## Flow ledger

| Operation | Trigger | Pending | Success destination | Success feedback | Failure recovery | Focus outcome | Source ref |
|---|---|---|---|---|---|---|---|
| Sign in | Submit credentials | Disable submit, preserve username, never persist password | Intended protected route | Dashboard appears | Inline credential/API message, keep form | Remains on submit button | `/auth/token`, `/auth/me` |
| Filter | Apply filter form | Keep current rows marked updating | Same route, page 1 | Updated results and count | Retain rows and offer retry | Focus stays on Apply | API list and analytics endpoints |
| Overview range | Apply UTC range and interval | Keep previous counts/chart marked updating | Overview with range encoded in URL | Summary and timeline use the selected interval | Retain prior data with retry; validation is inline | Focus stays on Apply | `/analytics/summary`, `/analytics/timeline` |
| Acknowledge | Alert action | Disable that row action only | Same alert list | Row status changes to acknowledged | Keep row new, inline retry feedback | Focus stays at action | `PATCH /alerts/{id}/acknowledge` |
| Create account | Admin submits a valid username, temporary password, and role | Disable the create action and retain the form | User management, first page | Inline success; clear all credential fields and refresh the register | Keep the form and show the API/validation message | Focus stays on submit | `POST /auth/users` |
| Change account status | Admin selects Activate or Deactivate | Disable only that account action | Same register | Update the row and announce the new status; deactivation revokes refresh sessions | Keep the prior status and show the API conflict/error | Focus stays at action | `PATCH /auth/users/{id}/status` |
| Expand details | View details | Immediate | Same route | Evidence/timestamps shown inline | Not applicable | Focus stays on disclosure | Detail schema |
| Logout | Header action | Disable while request settles | Login | Session cleared | Clear local session regardless of response | Focus username on arrival | `/auth/logout` |

## Navigation and responsive behavior

- **Route titles:** `Overview`, `Simulation`, `Capture history`, `Model & evaluation`, `Alerts`, `Flows`, `User management` (admin only), and `Sign in · Network observatory`.
- **Route errors / 403:** Missing session returns to sign-in with a safe same-origin return path. A 403 keeps the page visible and explains that the account cannot perform that action.
- **Route-state:** Overview, Simulation, Capture history, Model & evaluation, Alerts, and Flows are primary links; User management is added for administrators. Date ranges, timeline interval, filters, and pagination are query state.
- **Navigation transformation:** Fixed left rail on wide screens; compact horizontal nav above content on narrow screens.
- **Responsive tables:** Desktop semantic table; below 760px show equivalent record cards with all fields and actions.
- **Truncation:** IDs and endpoints may wrap; full exact values are available in detail expansion. Do not rely on hover for access.
- **Focus:** No sticky obstruction; route changes focus the page heading.

## Overlays and feedback

- No dialogs or drawers in Step 8. Expand detail inline.
- Persistent API/stream state is inline and announced politely; mutation failure is kept beside the action.
- No transient toast for critical or actionable feedback.

## Async and resilience

- **Mutations:** Pessimistic acknowledgement and account-status changes; duplicate submission blocked for the affected record. Account creation clears the password field after success.
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
- User management navigation is shown only for administrators. The API enforces admin-only listing and mutations, prevents self-deactivation and last-active-admin lockout, and audits status changes without credentials.
- No clipboard action in Step 8.

## Verification

- **Static commands:** `npm run typecheck`, `npm test`, `npm run build`, premium UI `audit_project.py --mode strict`.
- **Browser/device/theme:** Chromium/desktop and narrow phone width; graphite and brass dark theme.
- **Accessibility:** Keyboard through sign-in, navigation, filters, chart interval, tables, disclosures, and acknowledgement; inspect focus and reduced motion. Overview charts include an accessible name and a text table of bucket values.
- **Sibling flow:** Alerts and flows establish the shared table pattern; Overview and Capture history extend it with aggregate and run-level evidence.
- **Evidence:** Results are recorded in `docs/PROGRESS.md`; no test data is shown as production telemetry.

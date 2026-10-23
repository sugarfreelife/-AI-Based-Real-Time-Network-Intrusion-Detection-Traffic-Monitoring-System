---
version: alpha
name: "Network observatory"
description: "A calm, evidence-first workspace for reviewing persisted network flows and intrusion alerts."
colors:
  primary: "#214E45"
  ink: "#202925"
  muted: "#68736D"
  canvas: "#F3F1EA"
  paper: "#FFFEFA"
  paper-muted: "#EAE8DF"
  line: "#D9D8CE"
  forest: "#214E45"
  forest-soft: "#E1ECE7"
  rust: "#A95739"
  critical: "#9F332D"
  high: "#A3442D"
  medium: "#8A640F"
  low: "#35685C"
  focus: "#145D92"
typography:
  sans:
    fontFamily: "Aptos, Segoe UI, system-ui, sans-serif"
  mono:
    fontFamily: "Cascadia Code, SFMono-Regular, Consolas, monospace"
rounded:
  DEFAULT: "0.5rem"
  sm: "0.25rem"
  md: "0.5rem"
  lg: "0.75rem"
  full: "9999px"
spacing:
  section-gap: "1.5rem"
  page-max: "90rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.paper}"
    rounded: "{rounded.md}"
    padding: "8px 13px"
    typography: "{typography.sans}"
  card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "16px"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
  table:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
  navigation-active:
    backgroundColor: "{colors.forest-soft}"
    textColor: "{colors.forest}"
    rounded: "{rounded.md}"
  event-marker:
    backgroundColor: "{colors.rust}"
    rounded: "{rounded.full}"
  severity-critical:
    backgroundColor: "#F5E4E0"
    textColor: "{colors.critical}"
    rounded: "{rounded.full}"
  severity-high:
    backgroundColor: "#F7E9E0"
    textColor: "{colors.high}"
    rounded: "{rounded.full}"
  severity-medium:
    backgroundColor: "#F3EDDB"
    textColor: "{colors.medium}"
    rounded: "{rounded.full}"
  severity-low:
    backgroundColor: "#E5EEE8"
    textColor: "{colors.low}"
    rounded: "{rounded.full}"
  focus-ring:
    backgroundColor: "{colors.focus}"
  divider:
    backgroundColor: "{colors.line}"
  muted-copy:
    textColor: "{colors.muted}"
  page-canvas:
    backgroundColor: "{colors.canvas}"
  inset-surface:
    backgroundColor: "{colors.paper-muted}"
---

# Network observatory design system

## Overview

### Creative North Star

The visual reference is a field engineer's well-kept paper log beside a calibrated instrument: warm paper, measured labels, fine rules, and compact monospaced network identifiers. The interface should feel reliable during investigation, with severity expressed through legible color and language rather than alarm-like glow.

### Product context and register

- **Audience and primary job:** Analysts, administrators, and viewers review stored network flows and explainable alerts; analysts and administrators can acknowledge alerts.
- **Target market(s) and evidence:** Academic NIDS project for a technical audience. The repository's project brief and API roles establish this scope; no country-specific consumer-market assumptions are made.
- **Locale(s) and language policy:** English UI, using browser locale for date and time display. API timestamps remain timezone-aware ISO-8601 values.
- **Usage scene:** Desktop-first investigation with dense tables, plus narrow-screen review on a phone. Prioritize scan speed and exact endpoint readability.
- **Register:** Product interface on all routes, including login. No marketing surface.
- **Memorable signature:** A thin packet-trace rule with one rust-colored event marker anchors the page header and active navigation.
- **Restraint:** Keep navigation, filters, and tables familiar; avoid decorative noise, fabricated telemetry, and dashboard gauges without a real source.
- **Anti-references:** Avoid black neon SOC dashboards, glowing maps, pseudo-live counters, and red/green-only states because they obscure the product's persisted evidence and role boundaries.
- **Token ownership/runtime mapping:** `frontend/src/styles.css` owns the runtime CSS values. Tailwind's `@theme inline` aliases those variables; this document mirrors the accepted values. Change CSS and this file together. `npm run typecheck` and `npm run build` are the current token drift gates; the premium UI audit is recorded in `docs/PROGRESS.md`.

## Colors

The canvas is warm stone (`canvas`) with paper panels (`paper`) and quiet inset surfaces (`paper-muted`). `ink` and `muted` establish text hierarchy; `line` separates groups without shadow-heavy cards. Forest (`forest`) marks primary actions and active navigation. Rust (`rust`) is the single expressive signal marker. Severity colors (`critical`, `high`, `medium`, `low`) always appear with readable severity text. `focus` is reserved for the keyboard focus ring. The first implementation supports a light theme only; a dark theme is not implied.

## Typography

Use the OS sans stack for headings, controls, prose, and labels. Use the monospace stack for IP addresses, ports, UUIDs, protocol tags, and precise event metadata. Keep sentence case for controls and headings. Render dates in the browser's locale and timezone while preserving their full exact ISO timestamp in accessible detail text. The language is English; no alternate-script or Japanese-specific line-breaking policy is claimed.

## Layout

The application uses a fixed-width navigation rail on wide screens and a compact horizontal navigation on narrow screens. Main content is capped at 90rem with 1.5rem section gaps and 1.5rem page gutters, reducing to 1rem on small screens. Tables use a semantic table at desktop widths and stacked records on phones. Every queryable list reads filters and page from the URL. Avoid fixed-height data panels; preserve row geometry while busy.

## Elevation & Depth

Hierarchy comes from canvas/paper contrast, thin borders, and a restrained header rule. Cards do not float. Shadows are limited to the login panel and transient focus treatment. No blur or glass effects.

## Shapes

Controls use 0.5rem corners, small status pills use fully rounded ends, and panels use 0.75rem corners. Tables use straight ruled rows. Focus rings remain visible beyond the corner radius.

## Components

### Foundational visual states

Buttons and fields keep geometry stable across hover, focus, pressed, disabled, and busy states. Focus uses a 2px blue ring with offset. Busy actions retain their label and width and expose `aria-busy`. Loading uses a small rotating line mark and a reserved status area; reduced-motion disables rotation. Errors use text and a left rule, not color alone. Empty results use a quiet outlined icon and a next action.

### Buttons and actions

Primary forest solid buttons are reserved for login, filter application, and acknowledgement. Secondary buttons use paper fill and a line border. Destructive actions are not present in this UI. Icon buttons have visible tooltips and accessible names.

### Navigation and data display

The side rail identifies the active Overview, Capture history, Model & evaluation, Alerts, or Flows route with a forest-tinted panel and packet-trace marker. Severity badges include a text label. Read-only tables have explicit headers and stable sorting order from the API. Recharts overview timelines use persisted API counts within the selected range and label UTC intervals in the viewer's local timezone. Model evaluation tables show only reports that pass the configured artifact and report checks; unavailable model state remains explicit. The Alerts page chart displays only severity counts from the currently loaded page and names that scope directly.

### Forms and overlays

Inputs have visible labels, inline validation, and an explicit show/hide password button. Filter selects use native HTML controls; platform popup styling is intentionally accepted. Record details expand inline instead of using a native modal. Errors and connection state remain inline.

### Iconography

Use Lucide React outline icons at 16–20px with a 1.75px stroke. Decorative icons are hidden from assistive technology; icon-only controls require an accessible name and tooltip.

### Motion

Only short state transitions (120–180ms) and the loading mark animate. Honor `prefers-reduced-motion: reduce`; there are no ambient loops.

## Accessibility

Target WCAG 2.2 AA: semantic landmarks and tables, explicit field labels, visible focus, minimum 24px interactive targets (44px preferred for primary touch actions), no color-only meaning, live announcements for stream/connectivity changes, and reduced-motion support. Narrow layout retains all data and actions.

## Content

Use direct operational language. Dates are localized for reading and exact UTC/offset strings are available in details. Empty states make clear that no persisted records match; they never imply a detection result. Unknown prediction status is shown as not scored, not as benign.

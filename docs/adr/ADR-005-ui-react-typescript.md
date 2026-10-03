# ADR-005: React + TypeScript for the UI, which is the product's main face

- **Status:** accepted
- **Date:** 2026-10-03
- **Phase:** 3 (amends ADR-002)

## Context

The UI is to be Ledgerline's main face: an attack simulation lab, evidence and verification views, a policy studio, an approval inbox and operational dashboards (see `docs/research/ui-research.md`). It needs animated flow graphs, live updates, editors, diffs and charts. ADR-002 chose Python for everything, with one Go exception (`tlogd`).

Options considered: Reflex (Python compiled to React, pre-1.0), NiceGUI (Python, Vue-based, stable), FastAPI + htmx (server-rendered), and React + TypeScript.

## Decision

The UI is a **React + TypeScript** single-page app in `web/` (Vite, Tailwind + Radix, React Flow, TanStack Query, Monaco, Recharts, Motion; Vitest + Playwright; Biome). It is the **second exception** to Python-only. The backend stays Python: a FastAPI app in `src/ledgerline/api/` serves a REST + WebSocket API and, in production, the built UI. `ledgerline ui` starts both on 127.0.0.1.

Rules that keep the exception contained:

1. **Python is the source of truth.** API types are generated from FastAPI's OpenAPI schema with `openapi-typescript`; CI fails if they drift.
2. **No security decisions in the browser.** The UI only displays and requests. Enforcement, policy and verification happen in Python. The one planned exception is an *independent* in-browser bundle verifier (Phase 9), which deliberately adds a second implementation.
3. **The UI server is hardened** like any security product: localhost binding, startup token, `Origin`/`Host` validation, a strict Content-Security-Policy.

## Consequences

- Full access to the React ecosystem for the visual, interactive features that make Ledgerline's value visible.
- A second toolchain (Node 24, npm) in development and CI from Phase 3; a `web` CI job runs lint, type checks, unit tests, build and Playwright.
- The maintainer learns TypeScript; the guide gains a "React for Java developers" section.
- Every phase from 3 on ships a thin UI slice next to its backend work, with polish in Phase 8.

## Alternatives considered

- **Reflex.** Python with React underneath, but pre-1.0 (v0.9) API churn, and complex components still need React wrappers.
- **NiceGUI.** Stable and simple, but less suited to a polished, animation-heavy flagship UI.
- **FastAPI + htmx.** Great for forms and tables; weak for live animated graphs and editors.

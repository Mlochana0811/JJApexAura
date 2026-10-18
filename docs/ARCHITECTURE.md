# Architecture

## Reference inspected

`https://github.com/Mlochana0811/Stockflow-web.git`, commit `07e903a167a823850ef63e33027e4396a1285431`.

Its frontend contains `src/components`, `src/layouts`, `src/pages/<feature>/com`, `src/routing`, `src/data`, `src/lib`, and `src/styles`. Its `src/lib/auth.js` uses mock accounts. No backend was present in the inspected repository. This project follows that organization with original HR-specific implementation; no Stockflow inventory pages or mock authentication are used.

## Folder mapping

| Path | Responsibility |
| --- | --- |
| `frontend/src/main.jsx`, `App.jsx` | React entry and providers |
| `frontend/src/routing/AppRoutes.jsx` | Protected routes and invitation/reset routes |
| `frontend/src/layouts/AppLayout.jsx` | Shared workspace layout |
| `frontend/src/components/ui/` | Base UI-backed buttons and accessible modal |
| `frontend/src/components/sidebar/` | Role-specific navigation |
| `frontend/src/pages/dashboard/` | Dashboard, attendance clock, charts, company shortcuts |
| `frontend/src/pages/auth/` | Sign-in, first-password change, reset and invitation acceptance |
| `frontend/src/pages/resources/com/` | Reusable validated forms and detail/workflow panels |
| `frontend/src/data/resources.js` | Page definitions, labels and visible columns; not mock records |
| `frontend/src/hooks/useAuth.jsx` | Session state and role helpers for presentation |
| `frontend/src/lib/api.js` | Fetch, CSRF token handling and error propagation |
| `backend/config/` | Settings and URL composition |
| `backend/core/` | Company, employee, user, salary history, original branding |
| `backend/leave/` | Leave, entitlements and HR request records |
| `backend/payroll/engine.py` | Decimal arithmetic and numeric validation |
| `backend/payroll/models.py` | Payroll states, effective salary, snapshots and calculation orchestration |
| `backend/payroll/exports.py`, `statutory.py` | Existing report formats, upgraded to snapshots |
| `backend/workforce/models.py` | Attendance, shifts, documents, loans, assets, audit and policy models |
| `backend/workforce/api.py` | HTTP controllers, explicit field allowlists, scoped querysets and form schemas |
| `backend/workforce/services.py` | Transactional workflows and authorization rules |
| `backend/workforce/reports.py` | New PDFs and bank schedule |
| `backend/*/migrations/` | Versioned database evolution |
| `backend/workforce/management/commands/` | Demo/import, email, reminders and legacy snapshot tooling |
| `scripts/` | Cross-platform setup, development launcher and backup/restore |
| `docs/` | Architecture, operation, migration, validation and limitations |

Django’s models/forms already provide ORM and validation layers. Adding an Express-style controller/repository abstraction to duplicate them would make maintenance harder. Feature apps and a shared service layer are used instead.

## Request boundary

The browser stores no payroll database and no bearer token. Authentication is a server session with an HttpOnly cookie. Mutations require Django’s CSRF validation. Navigation hides unavailable controls, but API authorization is authoritative. Querysets scope company HR to their company, managers to themselves/their team, and employees to their own records.

Payroll transitions run in transactions with row locks. Input writes lock their period before modification. Production concurrency depends on PostgreSQL; SQLite is provided for local development only. Historical amounts, employee details and company registration details are snapshotted. Reopening archives superseded results in the audit log before clearing them.

The audit trail is append-only through application endpoints, but is not a cryptographically tamper-proof external ledger. Database administrators can alter database content; apply operational access controls and backups.

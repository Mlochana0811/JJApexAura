# Validation record

Final checks: 15 October 2026, Linux, Python 3.12, Django 5.2.18, SQLite, Vite 8.

- Django: 71 tests passed across core, payroll and workforce. Coverage includes company/team access, workflow restrictions, payroll snapshots, dated salaries, leave calendars, attendance corrections, loan posting and auth behavior.
- Django system checks: no issues. `makemigrations --check --dry-run`: no missing migrations.
- Frontend: 5 Vitest/Testing Library tests passed, covering API handling and resource forms.
- Oxlint completed successfully. Vite production build completed successfully with route-level chunks.
- Live HTTP check through the Vite proxy: app entry page, CSRF session initialization, login, forced password change, dashboard, employees, payroll and employee schema returned HTTP 200. Logout succeeded and subsequent protected access returned HTTP 401.
- The first live login attempt failed because the local database cache table had not been initialized. Running `createcachetable` resolved it; the supplied setup script and Docker instructions include this required step.
- Synthetic SQLite backup and isolated restore integrity checks passed during development.

## Limits of these checks

No real-browser visual or end-to-end interaction test was completed; Chromium installation failed in this environment. Windows launcher scripts were inspected but were not executed on Windows. Docker/PostgreSQL, external SMTP delivery, production TLS and bank/statutory filing acceptance were not tested. Automated tests do not certify regulatory compliance or exhaustively cover every possible workflow.

Only synthetic demonstration data was used for these checks. Databases, credentials, uploaded employee documents and original employee seed records are excluded from the distribution.

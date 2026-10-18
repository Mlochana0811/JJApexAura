# Jay’s HR Suite — v2

A runnable full-stack HR and payroll application, expanded from the supplied Jay’s HR v1.5 project. React uses the same principal frontend tools and page-oriented organization as the referenced Stockflow repository. Django remains the backend so the original payroll engine, migrations, templates, and EPF/ETF exports can be retained and improved.

**Start with the local demo.** No real employee records or credentials are bundled. Sample data is fictional and only created when requested.

## Quick start — Windows

Install Python 3.11+ and Node.js 22.12+ or 24 LTS. Open this extracted folder in VS Code.

Double-click `setup-demo-windows.cmd`, or run:

```powershell
python scripts/setup.py --demo
```

The setup prints a newly generated temporary password for four demo accounts:

- `demo.admin`: all-company payroll administrator
- `demo.hr`: company HR
- `demo.manager`: assigned-team manager
- `demo.employee`: employee self-service

Each account must change its temporary password at first sign-in. Keep the password printed in your terminal. Setup does not reset an existing installation.

Then double-click `start-windows.cmd`, or run:

```powershell
python scripts/dev.py
```

Open **http://localhost:5173/app/**. Leave the terminal open. Press Ctrl+C to stop.

The `.cmd` launchers use `npm.cmd`, avoiding PowerShell’s `npm.ps1` execution-policy issue. If Python is only available as `py`, run `py scripts/setup.py --demo` and `py scripts/dev.py`.

## Quick start — macOS/Linux

```bash
python3 scripts/setup.py --demo
python3 scripts/dev.py
```

For a clean installation without sample employees, omit `--demo`. Setup prompts you to create a system administrator. Create companies and reviewed payroll policies after signing in.

## Included modules

| Module | Implemented behavior |
| --- | --- |
| Companies | Separate company data, working calendars, payroll settings, original logo/branding editor |
| Accounts | Session login, CSRF protection, forced initial password change, email invitations, password reset, server-enforced roles |
| Employees | Records, reporting manager, salary history, emergency contacts, bank/EPF details, resignation and account deactivation |
| Attendance | Check-in/out, breaks, worked hours, lateness, overnight sessions, correction approval |
| Scheduling | Shifts, dated employee rosters, company holidays |
| Leave | Types, employee/year entitlements, overlap checks, company workdays, cross-year allocation, approval/cancellation, no-pay payroll import |
| Communication | Company announcements, read acknowledgements, in-app notifications, HR-initiated or employee-initiated request threads |
| Documents | Private authenticated downloads, uploads up to 10 MB, expiry dates and reminder job |
| Loans | Requests, approval, installments, outstanding balances, automatic payroll deductions and repayment posting at lock |
| Equipment and lifecycle | Asset assignment/return, onboarding and offboarding checklists |
| Payroll | Dated salary calculation, partial-month proration, input validation, reviewed policy versions, contribution/tax calculation, manual reviewed APIT overrides, audit, approval, final locking, separate payment status |
| Reporting | Payslip PDF, original salary-sheet Excel/PDF, EPF e-return/Form C detail and ETF schedules, generic bank schedule CSV, variance, attendance, salary/service letters, internal annual earnings statement |
| Delivery | Email invitations/reset, individual payslip email, batch payslip email command, console email backend for development |
| Operations | Migrations, automated tests, Docker/PostgreSQL configuration, SQLite backup and isolated restore verification |

The four demo businesses are Call Center, IT Solutions, Gem & Jewellery, and Property. Only Call Center has sample staff. Company names and records are editable.

## Stack and organization

- Frontend: React JSX, Vite, Tailwind CSS, React Router, Base UI, Lucide, Recharts, Geist font, Oxlint.
- Backend: Django 5.2, feature apps, scoped JSON API and shared workflow services.
- Local database: SQLite. Multi-user deployment: PostgreSQL via Docker Compose.
- Tests: Django test runner; Vitest and Testing Library for frontend behavior.

See [Architecture](docs/ARCHITECTURE.md) for the folder mapping and [Feature notes](docs/FEATURES-AND-LIMITS.md) for precise behavior and remaining deployment-specific work.

## Monthly payroll workflow

1. HR opens the month. Only the previous recurring welfare amount is optionally carried forward.
2. HR enters monthly inputs. Use **Import approved no-pay leave** and **Import roster overtime** if appropriate, then review the resulting values. Manual loan recovery is additional to automatic loan installments.
3. HR submits; system admin processes using the policy effective at the start of the month.
4. HR reviews the results/variance and approves. Employees can see approved payslips.
5. System admin locks. Scheduled loan repayments are posted exactly once.
6. HR downloads the bank schedule and records a payment reference after payment occurs outside this app.
7. Download statutory files and record the submission reference after actual filing.

Inputs cannot be edited after submission. Admin must reopen a submitted/processed/approved month first; this archives and removes superseded calculations. Locked months cannot be reopened. Record corrections as later-period adjustments.

## Email

Development prints emails to the backend terminal. To actually deliver email, configure `.env` with a working SMTP account and `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`. Set `PUBLIC_URL` to the externally reachable frontend URL ending in `/app`.

Commands are opt-in; nothing is scheduled by this source package:

```bash
# Run in backend with the project virtual environment
python manage.py email_payslips --period 1          # dry run
python manage.py email_payslips --period 1 --send   # send approved, not-yet-emailed payslips
python manage.py notify_expiries                  # daily reminder job
```

Schedule with your server’s cron or Windows Task Scheduler after configuring SMTP. Email delivery can be at-least-once if the mail server accepts a message and the process fails before recording completion.

## Docker / PostgreSQL

Copy `.env.example` to `.env`, set unique `SECRET_KEY` and `POSTGRES_PASSWORD`, and keep `DEBUG=true` for a local-only demo. The web port binds to localhost.

```bash
docker compose build
docker compose up -d db
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend python manage.py createcachetable
docker compose run --rm backend python manage.py collectstatic --noinput
docker compose run --rm backend python manage.py createsuperuser
docker compose up -d
```

Open http://localhost:8080/app/. For a demo instead of `createsuperuser`, run `seed_demo --password YOUR_TEMPORARY_PASSWORD` explicitly. Do not run seed commands against production data.

Docker files are supplied; Docker was not available for execution in the build environment. Production HTTPS/reverse-proxy configuration is described in [Operations](docs/OPERATIONS.md).

## Tests

```powershell
# Windows, from project root
.venv\Scripts\python.exe backend\manage.py test core payroll workforce --verbosity 1
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

Run Django tests from `backend/` when using direct shell commands so automatic discovery includes all apps:

```bash
cd backend
../.venv/bin/python manage.py test
```

See [Validation](docs/VALIDATION.md) for checks actually performed and their limits.

## Existing data

The supplied ZIP contained source and seed JSON, not a live database. Real employee data is not embedded in this deliverable. To upgrade an existing installation, follow [Migration](docs/MIGRATION.md); never replace your live database with a demo database. Original seed JSON can be imported explicitly; CSV import is also available.

## Important scope

This is an implemented application package, not a hosted service or a certification of payroll compliance. SMTP, production hosting, backups/scheduling and your reviewed payroll rules require configuration. The bank file is a generic payment schedule, not a certified bank-specific upload. The annual report is not an official T-10 certificate. See the feature notes for items requiring organization-specific implementation or review.

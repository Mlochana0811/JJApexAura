# Operation and deployment

## Local operation

`python scripts/setup.py --demo` installs a project virtual environment and the locked frontend dependencies, migrates a local SQLite database, creates the cache table, and explicitly seeds synthetic demo data. It generates a unique local secret and demo password. `python scripts/dev.py` starts Django and Vite together.

The React frontend lives at `/app/`; `/api/` goes to Django. Original `/branding/`, `/payroll/` export pages and printable `/payslip/` pages remain server-rendered. The development proxy shares cookies and CSRF handling with the API.

## Production

Use PostgreSQL, not SQLite, for concurrent payroll processing. Make a tested backup before deploying migrations. Configure a unique SECRET_KEY of at least 50 characters, `DEBUG=false`, exact `ALLOWED_HOSTS`, HTTPS `CSRF_TRUSTED_ORIGINS`, externally reachable `PUBLIC_URL` ending in `/app`, and SMTP. Run migrations, `createcachetable`, `collectstatic`, and `check --deploy`.

The included Compose configuration is local-only: port 8080 binds to 127.0.0.1 and assumes HTTP. Production needs a TLS reverse proxy. Its trusted HTTPS signal must reach Django correctly; the included Nginx HTTP example overwrites `X-Forwarded-Proto` with its own scheme. Configure the TLS terminator and internal proxy deliberately so Django sees `https`, without trusting arbitrary internet-supplied forwarded headers. Do not simply expose the local Compose file as production.

Serve only `/media/logos/` publicly. `/media/private/` must never be exposed by a static server. Documents are streamed by `/api/files/<id>/` after authorization. Retain uploaded media and the database together in backups. Restrict access to database, media and backup volumes. Secrets belong in deployment secret storage, not Git.

Production settings fail if the development secret is still used. Secure cookies, HTTPS redirect and HSTS are enabled when DEBUG is false. HSTS should be enabled only after your entire domain/subdomain HTTPS configuration is correct; adjust the setting for your actual infrastructure before first deployment.

## Backup and verified restore

SQLite local backup:

```bash
python scripts/backup.py
python scripts/verify_restore.py backups/hr-backup-YYYYMMDD-HHMMSS.zip restored-test
```

Use the actual generated filename (it includes microseconds). Restore creates a new directory, verifies hashes and runs SQLite integrity checking. It never overwrites the live database. Test the restored copy using a separate environment and `JHR_DB` before any live replacement. Pause writes during a database+media backup when a consistent cross-file snapshot is required; SQLite’s online backup itself is consistent.

For PostgreSQL, use your platform’s `pg_dump` and restore tooling plus the media volume. Verify a restore into an isolated database, then run migrations/checks and sample reports. The supplied Python backup tool does not pretend to back up PostgreSQL.

Backups contain sensitive HR and bank data. Encrypt and restrict offsite storage; define retention and regularly rehearse recovery. Scheduling is performed on your infrastructure, not automatically by this ZIP.

## Jobs

Run `notify_expiries` daily. Run `email_payslips --period <id>` for a dry run, then add `--send` when ready. These jobs do not execute merely because the source is installed. Configure your scheduler using the project virtual-environment interpreter. Monitor exit codes and SMTP errors.

## Administration

Initial admin creation is by `createsuperuser`; public admin sign-up is intentionally unavailable. HR invites employees; system admin can subsequently grant manager or client-HR roles to an existing employee-linked account. Operational payroll/leave admin models are read-only in Django admin; use the application workflows. Record payment only after actual external settlement. Record statutory references only after filing.

## Verification before live use

Use your own sample payslips to reconcile salaries, leave, EPF/ETF, APIT, partial months and deductions. Have payroll policy values and official output formats reviewed. Run through employee, manager, company HR and admin roles; verify permissions and backup recovery in your deployment. This delivery's validation does not substitute for deployment acceptance testing.

# Admin-managed login accounts

Sign in as Admin, open People, then open an employee's details. Use Create login account to enter a unique username, login email, temporary password and Employee or HR role. The account belongs to that employee's company. Existing accounts cannot be overwritten by this form.

Give the temporary password to its intended user securely. The system does not email or display it after saving. The user must change it at first login before accessing portal features. Password validation and hashing use Django's existing authentication system; passwords are excluded from audit records.

Alternatively, Admin can use Email account invitation. The invited person chooses their own username/password; the resulting account starts as Employee. Admin can then use Change existing account role to assign HR, Employee or the existing Manager role. HR and employee users cannot create accounts, issue invitations or change roles through these endpoints. HR can still maintain employee records. Users retain their own password-change/reset functions.

Direct creation invalidates outstanding invitations. Only active employees in active companies can receive new accounts/invitations. System Admin/superuser accounts cannot be changed through these employee role controls. Account creation and role changes are audited.

This source archive includes the previous automatic employee payroll rows, EPF selection and payslip templates. Back up and stop the existing app; copy source while preserving .env, .venv, backend/db.sqlite3 and backend/media. No dependencies or migrations were added for this account update. Restart with `python scripts/dev.py` from the project root. Production/Vercel configuration has not been added.

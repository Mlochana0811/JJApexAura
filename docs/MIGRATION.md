# Upgrade from v1.5

The supplied ZIP had no `db.sqlite3`; it included source and an initial employee JSON file. The new package does not embed that private seed data or create real accounts automatically.

1. Stop writes and back up the old database and media. Keep an untouched copy.
2. Install the new dependencies in a separate directory/environment. Do not seed the demo into the old database.
3. Point `JHR_DB` to a **copy** of your old SQLite database (or use your own reviewed PostgreSQL migration process). Copy old logos into the new media directory.
4. Run `python manage.py migrate` and `python manage.py createcachetable` from `backend/`.
5. Run `python manage.py freeze_legacy` to inspect missing historical snapshots. v1.5 did not preserve historical identity/bank details; they cannot be reconstructed from its database. After reviewing the old records, `freeze_legacy --accept-current-details` freezes available master details and explicitly marks payslips as backfilled. Preserve original exported payslips as evidence.
6. Review user-company-employee links, and company/employee dates, salary history and EPF identifiers.
7. Create a reviewed payroll-policy version effective before the next payroll month. No real policy is automatically certified.
8. Reconcile a copied month's results with your old export. Reopening deliberately archives and clears calculated results; locked periods remain locked.
9. Rehearse a full workflow on the copy before switching your deployment.

If you only have the original seed JSON, the retained `setup_initial_data` importer requires an explicit source path and creates temporary logins. Review its basic/allowance mapping before importing. It should only be run once in a test copy; it can update matching employees. CSV import is safer for adding new records without overwriting existing employees:

```bash
python manage.py import_employees employees.csv --company CALL
python manage.py import_employees employees.csv --company CALL --commit
```

Required CSV headers: `emp_no,full_name`. Optional headers: `email,department,designation,phone,nic,bank_name,bank_account,epf_no,basic_salary,join_date` (ISO date). Dry-run validates all rows; import is transactional. Create the company first. CSV import does not create accounts; use invitation actions after review.

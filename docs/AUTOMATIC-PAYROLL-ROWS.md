# Automatic employee rows and EPF selection

Select New salary sheet, then the company. All employees currently marked Active in that company load automatically. The Add employee, Add row and Remove controls have been removed from this screen. Employee records are still managed in People.

Opening a draft retains all its saved rows and entered amounts, and includes any active employees missing from that draft. Save the draft to retain newly included rows. Finalized sheets remain unchanged. This is a current-active roster, not a reconstruction of historical employment for the selected month.

HR can edit basic salary and select an EPF calculation per employee:

- Use basic salary: EPF salary follows the edited basic salary automatically.
- Separate EPF salary: HR enters the qualifying earnings amount independently. This is the default and preserves existing sheets.

The server validates the selection and recalculates linked amounts before saving. The existing Excel export uses the saved EPF salary and rate. Changes to basic salary here apply to this monthly worksheet; permanent effective-dated salary changes remain under Salary changes. Current master salary is suggested; dated changes and proration must be reviewed manually.

Qualifying EPF earnings can include allowances and other remuneration. Basic salary alone is not necessarily the statutory contribution base. HR must review the appropriate amount. Official source: https://epf.lk/?p=171 . This worksheet remains separate from statutory payroll and payslip calculation; these selectors do not change those workflows.

## Installing

Stop the app. Back up your existing folder and database. Copy the updated source into the existing project, preserving .env, .venv, backend/db.sqlite3 and backend/media. This archive includes the previous payslip formats and navy/teal theme. No new database migration is needed for this change; run migrate to apply any earlier outstanding updates.

From the project root in PowerShell:

```powershell
.\.venv\Scripts\python.exe backend\manage.py migrate
python scripts/dev.py
```

Dependencies have not changed, so an existing successful dependency installation does not need npm ci again. If dependencies were never installed successfully, stop the app before running `npm.cmd --prefix frontend ci --include=dev`.

# Salary template and payroll integration

New salary sheets follow the supplied Jay's HR monthly salary upload workbook. Existing sheets keep their earlier format and values. Historical payroll is not converted or recalculated by migration.

## Workflow

1. Payroll > New salary sheet: select company and month. Current active employees load automatically. Master basic salary and aggregate allowances are suggestions: EPF-able allowance goes into Other EPF-able allowance, and fixed allowance into Other allowance. Review dated salary changes, employment dates and monthly pay yourself.
2. Edit basic salary, six named allowances, no-pay days, OT hours, bonus, advance, welfare, loan recovery, other deductions and remarks. Set allowance EPF/ETF flags to Yes/No. Each flag applies across the sheet, matching row 7 of the workbook.
3. Upload salary Excel previews the supplied template. Emp No must match an existing employee in that company. Missing rows retain website values. Company code/month, if filled, must match. Company settings control no-pay and OT; workbook F2/F3/H3 are not trusted. Formulas in A:Q, duplicates, unknown employees, invalid values and malformed files are rejected. Grey R:W check formulas are ignored and recalculated.
4. Save draft, download the populated Excel, review and finalize. Checks use the template's 8%, 12% and 3% and show net before APIT, regardless of individual eligibility.
5. Apply to open payroll month replaces matching monthly inputs after confirmation. The month is created if necessary. Unmatched payroll inputs are retained. Previous APIT overrides on affected rows are cleared for review. This action does not approve, pay or email anything.
6. Review Statutory payroll and monthly inputs. A reviewed payroll policy is required. The existing APIT workflow applies; bonus requires a reviewed override for applicable employees. Process and approve using existing permissions, then download payslips or the processed Excel report.

Transferred monthly pay overrides salary suggestions for that payroll month. Employee master pay and permanent salary history remain unchanged. A second joining/leaving proration is not applied. Employment dates must permit inclusion in the month. Later monthly-input changes affect payroll, not the finalized source sheet.

## Calculations and reports

No-pay proportionally reduces fixed pay using the company divisor. OT uses basic salary and company settings. Imported rows use template rounding. Payroll applies reviewed policy rates, employee eligibility, APIT and automatic approved-loan deductions; final pay can differ from worksheet checks. Transfer blocks manual loan recovery where an approved loan also exists, to prevent overlapping recovery.

Payslips use saved allowance names/values. Processed payroll using one template configuration exports the template layout plus APIT and Net pay after APIT. Calculated columns contain payroll snapshot values, including automatic loan recovery. This is a report, not an upload input. Mixed or legacy payroll keeps its existing detailed export. The PDF salary summary retains its existing aggregated layout.

The supplied template includes Salary advance and Loan recovery, so these remain. Loan/payroll histories are retained. The worksheet does not certify the legal treatment of allowances; HR must review classifications.

## Install

Back up your database/media, stop the app, and copy updated source into the existing folder. Preserve .env, .venv, backend/db.sqlite3 and backend/media. Two additive migrations store template configuration and monthly salary overrides. From the project root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py migrate
python scripts/dev.py
```

Dependencies have not changed. Earlier Admin account, payroll and payslip updates are included. Vercel deployment configuration is not included.

## Verification

Backend tests cover formulas, allowance flags, access isolation, upload validation, Excel layout and payroll handoff/export. Frontend tests cover automatic rows, allowance editing, save and export. Lint and production build passed. Live email delivery and Microsoft Excel desktop were not tested.

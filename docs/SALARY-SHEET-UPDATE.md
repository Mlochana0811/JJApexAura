# Salary sheet update

Based on repository commit 51238ce and the supplied salary workbook. No employee names or salary records from the reference workbook are included in the source or automatically imported.

## Use the new screens

1. Add employees under People. This form now ends with Emergency contact.
2. Payroll > Employee payroll settings: edit bank details, EPF membership/eligibility, APIT applicability, statutory name fields and notes. Existing stored values are preserved.
3. Payroll > Salary changes: set effective-dated basic salary and allowances. New employees initially have zero salary until configured. An entry on the same effective date supersedes an older entry for calculation/suggestions.
4. Payroll > Salary sheets > New salary sheet: select a company and month, add employees, and fill amounts.
5. Save draft, review the total, then Download Excel. Draft exports are labeled DRAFT. Finalize locks the saved sheet against edits. Negative amounts payable may be saved for review as drafts but must be resolved before finalization.

## Workbook matching

The export keeps the latest reference layout: headers on row 4, names in B, Basic Salary C, EPF Salary D, Leave Deductions E, Welfare F, Salary Advance G, EPF H and Salary Amount I. Notes J, Appraisal K, New Salary L and Format % M are optional. One export contains one selected month, with dynamic row count and totals. Earlier reference sheets called Welfare “Futsal”; this implementation uses the latest “Welfare” label. Formatting is recreated in a consistent green table rather than copying historical cell formatting or private data.

EPF = ROUND(EPF Salary × entered EPF rate / 100, 2).
Salary Amount = Basic Salary − Leave Deductions − Welfare − Salary Advance − EPF.

Enter a monthly basic salary amount directly (including a daily-pay total when applicable). Leave deductions are entered as currency, not days. A blank required amount is rejected; use zero where appropriate. EPF rate starts at 8% for eligible employees as a template suggestion, with EPF salary initially zero for explicit review. This is not a statement of legal contribution eligibility or the correct contribution base.

Unlike some historical source formulas, every row refers to its own EPF base. Optional appraisal/new-salary/percentage columns are reference inputs: they do not alter current net salary or salary history. Totals include every entered employee. Formula results refresh when opened in Excel or another compatible spreadsheet application; the application also displays server-calculated totals.

## Relationship to existing payroll

This is a manual salary worksheet, not a replacement calculation engine for statutory payroll. It does not post loan repayments, calculate APIT/ETF/overtime, generate payslips, or transfer money. Those workflows and existing months remain at Payroll > Statutory payroll (`/app/payroll-runs`). Do not treat a worksheet and statutory run as two separate payments for the same employee/month.

The sheet snapshots names and entered values. Later employee changes do not change the saved export. Updating a draft refreshes names from the current employee record. API access is restricted to Admin/HR and scoped by company. Revision checks prevent stale saves; finalization and saves are audited.

## Upgrade an existing Windows installation

Back up your database and media before updating. Stop the app. Apply the code update to your existing folder, preserving `.env`, `.venv`, `backend/db.sqlite3`, and `backend/media`. Do not run demo seeding again.

From the project root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py migrate
npm.cmd --prefix frontend ci --include=dev
python scripts/dev.py
```

Production Docker installations must rebuild images and run migrations using their existing production configuration. No schema fields or existing employee/payroll rows are deleted by this migration; it adds a SalarySheet table.

## Validation

80 backend tests and 7 frontend tests passed. New coverage includes company/role isolation, invalid amounts, revision conflicts, finalization, negative-pay drafts, formula injection prevention, workbook formulas, employee field relocation and the save/export UI flow. Frontend lint and production build passed. Real-browser visual review and Microsoft Excel desktop recalculation were not performed in this environment.

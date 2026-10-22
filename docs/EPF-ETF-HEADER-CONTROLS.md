# Allowance contribution controls and payroll settings

Option 2 places separate EPF and ETF Yes/No selectors underneath each of the six allowance headers. Yes includes that allowance in the relevant contribution base. These controls affect the sheet calculation, Excel formulas, payroll preview and processed payroll. Basic salary remains included. This update does not add contribution switches to employee identifiers, deductions or calculated output columns.

New sheets default food and cost-of-living allowances to inclusion. A draft may be saved for review, but finalization requires a contribution review note if either of these allowance slots is excluded from EPF or ETF. A note is an audit record, not a legal exemption. Verify actual payment classification with your payroll adviser; changing a header label does not change its legal treatment.

Official references reviewed 22 October 2026:
- https://epf.lk/?page_id=811 — EPF contribution rates and earnings components.
- https://etfb.lk/employers-faq/ — ETF employer contribution and earnings components.

EPF normally comprises 8% employee and 12% employer contributions. ETF is 3% employer funded. Food allowance is included in the published earnings definitions. Employer contributions do not reduce employee net salary. Existing payroll policies and employee eligibility remain in effect.

Column display settings now live under Employee payroll settings > Salary sheet columns. Select a saved draft, set Yes/No and save. Settings are per saved sheet, not company defaults. They do not affect contribution eligibility or payroll amounts. Reopen a sheet after changing its settings; stale revisions are rejected. Finalized sheet layouts and calculations remain immutable.

Finalized sheets have Remove (archive). Archived sheets are hidden from the normal list; use Show archived sheets to view or restore them. Archiving retains the original, audit history, company/month reservation, and linked payroll/payslips. It does not cancel payroll or allow another sheet for the same month. An archived sheet cannot be applied to payroll until restored. Draft deletion remains unchanged.

Excel exports use row 6 for ETF flags and row 7 for EPF flags. Existing upload templates without separate ETF flags retain the shared-flag interpretation. Old saved sheets without an ETF flag use their existing EPF flag for ETF until reviewed; no historical figures are rewritten.

## Install on Windows
Stop the application and back up your database and project. Copy the updated source, preserving .env, .venv, database, media and node_modules. From the project root run:

    .\.venv\Scripts\python.exe backend\manage.py migrate
    python scripts/dev.py

The new migration adds the archived flag. No additional packages are required.

# Salary sheets and optional columns

Draft sheets support create, view, edit, update and audited deletion with revision checks. Finalized sheets remain immutable and can be archived/restored using the list actions.

Column visibility is under Employee payroll settings > Salary sheet columns, with a checkbox for every standard column in the selected company. Settings apply to existing drafts and new sheets. Checked displays the column; unchecked hides it in the sheet and Excel without changing salary calculations or saved amounts. Save column settings persists these choices. Previously deleted input values cannot be recovered by selecting Yes.

Allowance headers contain one combined EPF/ETF contribution checkbox. There are no Add column, Edit header or Remove column buttons. Previously saved custom columns and renamed headers are preserved. Salary sheet CRUD buttons remain available.

Run migrations to install the company column settings model. No new dependencies. Back up your project and database before replacing source; preserve .env, .venv, media and database files.

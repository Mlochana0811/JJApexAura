# Salary sheets and optional columns

Draft sheets support create, view, edit, update and audited deletion with revision checks. Finalized sheets remain immutable and can be archived/restored using the list actions.

Column visibility is under Employee payroll settings > Salary sheet columns, with a dropdown for every column in the selected saved draft. Yes displays the column; No hides it in the sheet and Excel without changing salary calculations or saved amounts. Save/Update sheet persists these choices. Previously deleted input values cannot be recovered by selecting Yes.

Allowance headers contain separate EPF and ETF contribution dropdowns. There are no Add column, Edit header or Remove column buttons. Previously saved custom columns and renamed headers are preserved. Salary sheet CRUD buttons remain available.

No new migrations or dependencies. Back up your project and database before replacing source; preserve .env, .venv, media and database files.

# Salary sheets and optional columns

Draft sheets support create, view, edit, update and audited deletion with revision checks. Finalized sheets remain immutable.

Choose columns — Yes / No is a separate panel above the table, with a dropdown for every column. Yes displays the column; No hides it in the sheet and Excel without changing salary calculations or saved amounts. Save/Update sheet persists these choices. Previously deleted input values cannot be recovered by selecting Yes.

Table headers contain names only. There are no Add column, Edit header or Remove column buttons. Previously saved custom columns and renamed headers are preserved. Salary sheet CRUD buttons remain available.

No new migrations or dependencies. Back up your project and database before replacing source; preserve .env, .venv, media and database files.

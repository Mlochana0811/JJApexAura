# Selectable payslip formats

This update includes the previous salary-sheet changes and navy/teal website theme.

## Using the website

1. Admin: edit a Company and choose its Payslip template: Navy & teal or Classic gold.
2. HR: under Payroll > Employee payroll settings, record bank details and the optional Bank account holder name. If blank, the employee's name is used.
3. Use Payroll > Salary changes and the statutory payroll monthly inputs to configure pay. Process and approve the statutory payroll run.
4. Open a payslip and choose Payslip format, then Download payslip PDF. The Email action uses that selected format too.
5. On an approved or locked statutory payroll run, choose a format and Download all payslips PDF.

Company default uses the company's current selection; choosing a format does not change saved pay figures. Scheduled email uses the company default. Employee accounts can download only their own approved payslips. Combined downloads require HR/admin access within the permitted company.

## Document contents

Company name/contact header; month, employee and designation; earnings; deductions; net pay; employer contributions; bank details; computer-generated footer. Classic gold follows the example's section arrangement; Navy & teal uses the same arrangement in the website palette. The original company artwork and personal details are not bundled. This is a text company header, not a logo upload feature.

The document uses approved payroll snapshots. No-pay appears as a deduction and total earnings are shown before no-pay, so it is not deducted twice. Employer contributions do not reduce net pay. New runs snapshot company contacts and bank account holder name. Older runs without those fields use employee name for account holder and omit missing company contacts.

This changes document output, not salary/EPF calculation policy. It does not add new medical, stamp-duty or night-shift calculation fields. Those require a separate salary-component design. Manual salary worksheets remain independent and do not generate these payslips; use approved statutory payroll for this output. The example's allowance treatment is not a compliance rule.

## Update an existing Windows installation

Stop the app and back up your database and media. Copy this source update into the existing project, preserving `.env`, `.venv`, `backend/db.sqlite3`, and `backend/media`. Do not overwrite locally customized code without reviewing it. Do not re-seed demo data.

From the project root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py migrate
npm.cmd --prefix frontend ci --include=dev
python scripts/dev.py
```

The new migration adds company template selection and employee bank account holder name. Existing records are retained. Production installations must rebuild and migrate using their production configuration.

## Verification

Backend tests cover financial reconciliation, no-pay display, format validation, approval gating, employee access and combined downloads. Both PDF layouts were rendered and visually inspected using synthetic data. Frontend selector tests, lint and production build passed. No live email delivery or real-browser end-to-end session was performed.

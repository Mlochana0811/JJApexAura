# Jay's HR – Payroll & HR portal

This is phase 1 of Jay's HR, the payroll portal run by PD Accounting Services (Pvt) Ltd for its client companies.

## Who uses it

| Role | Login given by | Can do |
|---|---|---|
| **Jay's HR admin** | — | Everything for all companies. Processes payroll, locks months, edits settings at `/admin/`. |
| **Client HR** (one per company) | Jay | Adds and edits their own employees, enters monthly inputs, submits payroll, approves payroll, approves leave and answers HR requests. Sees only their own company. |
| **Employee** | Jay | Checks leave balance, applies for leave, sends requests to HR (letters, advances, detail changes) and views and prints approved payslips. |

Everyone must set their own password the first time they log in.

## Look and branding

- **Default look:** plain, calm Jay's HR theme in sage green with the Bold design (header filled with green).
- **Company branding:** each client can set its own look under **Branding**. They can upload a logo, and the main and second colours are picked from it automatically. They can also choose colours by hand or switch back to the Jay's HR default.
- **Where the brand shows:** their staff see the portal in the company's colours with the logo, and payslips carry the same logo and colours.
- **Readability:** colours too light to read are darkened automatically for text and buttons.
- **12 colour sets:** Mauve, Lavender, Dusty rose, Plum, Terracotta, Sand, Olive, Sage, Teal, Dusty blue, Navy, Slate.
- **4 page designs:** Soft, Bold, Minimal, Tinted.
- **Jay's HR default look:** set under Branding → "Jay's HR default look". It is used for your own screens, the sign-in page and any client without its own colours.

## Payroll rules

- **EPF and ETF base is "total earnings" as the EPF Act defines it:** employee 8%, employer 12%, ETF 3%.
  - **Included:** basic salary, EPF-able allowances (cost of living, special living, food allowance) and EPF-able monthly earnings (commission, piece rate, holiday pay).
  - **Excluded:** OT, bonus/incentives, reimbursed travel and "other" allowances.
- **No-pay days:** one day's pay is (basic + fixed allowance) ÷ 30. The basic part of the no-pay deduction also reduces the EPF base. The divisor can be set per company.
- **Overtime:** basic ÷ 240 × 1.5 per hour. The divisor and multiplier can be set per company.
- **APIT:** uses the resident rates in force from 1 April 2025 (Rs. 150,000 a month tax-free, then 6/18/24/30/36%). Check these against the IRD tables every year (`payroll/engine.py`).

## Carry forward and downloads

- **Carry forward:** when a new month is opened, last month's inputs (welfare, loans, advances, OT, no-pay, remarks and so on) are copied in automatically. The client changes only what is different. Untick "Start with last month's inputs" to start blank, or use **Copy <last month> again** to reload them.
- **Downloads:** each payroll month has **Download Excel** and **Download PDF** salary sheets. Both include totals, net salaries to bank, and EPF, ETF and APIT payable. Before processing, the download is marked **DRAFT** and is worked out from the current inputs.

## EPF & ETF files (per payroll month → "EPF & ETF files")

- **EPF e-Return:** `EVEMC.TXT` (Contribution Detail, one line per member) and `EVEMP.TXT` (Payment Summary), fixed-width ASCII, zipped. The EPF Department checks a new employer's first files before live submission.
- **EPF contribution detail in Excel:** the same fields in the EPF template order.
- **Form C details PDF:** member list with total earnings, 12%, 8%, totals and payment details.
- **ETF schedule:** PDF and Excel, monthly (R4/R1 support).
- **ETF half-yearly return (Form II):** Excel, from the company's payroll page.
- **Required first:** company EPF zone + employer number (Settings → Companies), and each employee's NIC and EPF member number. The page lists anything missing.

## Monthly cycle

1. **Client HR opens the month,** enters no-pay days, OT, advances, welfare and so on, then clicks **Submit**.
2. **Jay's HR clicks Process payroll,** which calculates every payslip.
3. **Client HR reviews and clicks Approve.** Employees can now see their payslips.
4. **Jay's HR locks the month.**

## Run it locally

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_initial_data      # loads Clever Growth + Synergy Core, creates logins
python manage.py runserver
```

Temporary passwords are written to `data/initial_logins.csv`. Hand them out, then delete the file.
Run the tests with `python manage.py test`.

## Imported data

`data/initial_employees.json` holds the employees found in Google Drive. Each person's **basic salary is set to Rs. 30,000**, the amount EPF has been paid on so far, and the rest of their pay is the **fixed allowance**. Change it with `--basic`, or edit employees in the portal.

## Coming next (phase 2+)

- Payslip PDFs emailed automatically.
- Bank transfer file.
- EPF C-form, ETF and APIT reports.
- Salary confirmation letter generator.
- Gratuity and year-end T-10.
- Deployment on a cloud server with HTTPS and daily backups.

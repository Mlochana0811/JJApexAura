# Feature behavior and limits

## Implemented and usable

All resources are database-backed. Forms are built from backend-approved schemas; server-side allowlists prevent clients from editing approval fields or roles through arbitrary payloads. The API has company/team scoping, private document endpoints, CSRF, session authentication, and login throttling.

Attendance supports one open session per person, non-overlapping approved corrections, break duration subtraction, late-minute calculation, and overnight roster selection. Overtime import uses completed rostered sessions only: `max(worked hours − expected shift hours, 0)`. It does not infer overtime for unrostered sessions or infer no-pay from missing check-ins. Review imported hours before submission. Approved no-pay leave has a separate explicit import action.

Leave supports company workweeks, holidays, per-year entitlements, requests spanning years, overlap prevention, half-days and pending reservations. Annual accrual, carry-over expiry and special maternity/other rules are configured manually through entitlement records; there is no automatic jurisdiction-specific entitlement engine. The inherited default leave types are examples, not legal advice.

Salary changes use effective dates. Fixed components are weighted across actual calendar days in the month; joining/leaving dates prorate eligible days. No-pay and overtime continue to use the company’s configured divisors. The current screen’s master salary can differ from a future scheduled salary; payroll reads dated history. Retroactive changes overlapping processed/approved payroll are blocked; reopen unlocked payroll or use later-month adjustments. Validate your company’s partial-month and no-pay convention before use.

Payroll rules have dated policy records. Processing requires a reviewed policy effective on or before the month’s first day. The regular-income APIT calculation uses that policy’s annual relief and marginal bands. Bonus/other-earnings cases require a manual reviewed APIT amount and explanatory note. There is no claim of automatic support for every APIT table, non-resident status, terminal benefit, secondary employment or tax-year reconciliation. Default/demo rates are test fixtures until reviewed.

Loans are interest-free fixed-installment schedules. Automatic repayments are snapshotted during processing and posted once at final lock. A changed balance may require reopening/reprocessing an unlocked payroll. An approved request records an HR decision; the app does not transfer loan money. External disbursement controls remain the organization’s responsibility.

Offboarding creates a checklist and deactivates the employee login. Dated leavers remain eligible for their worked payroll month. Final amounts can be entered through payroll adjustments. Checklist completion does not calculate or automatically deduct contractual penalties.

## External configuration / features not claimed as complete

- Production hosting, domain/TLS, SMTP credentials, backup destination and job scheduler must be configured.
- Docker/PostgreSQL infrastructure is supplied but was not executed in this environment.
- Bank schedule CSV is a generic review/payment list; bank-specific upload adapters and payment reconciliation against bank statements are not implemented.
- Statutory returns are the inherited EPF/ETF formats with approved/snapshotted data. Official acceptance, institution-specific formatting and changes in regulations must be verified before filing.
- Annual earnings PDF is an internal calendar-year statement, **not an official T-10 certificate**. Official T-10/APIT filing exports and a comprehensive gratuity/legal final-settlement engine are not implemented.
- Salary/service letters are generated for review/signature, not automatically signed documents.
- Documents use file extension/size validation and authenticated attachment downloads. Antivirus/content scanning, cloud object storage and a retention/deletion policy are deployment extensions.
- HR conversations are text threads. Supporting files can be uploaded in Documents; inline per-message attachments are not implemented.
- UI uses company logo and primary button color; the original server-rendered branding and report pages retain their full theme variants. Not every React surface changes to all four legacy visual styles.
- No biometrics, GPS geofencing, SSO/MFA, offline mobile mode, statutory automatic updates, recruitment pipeline or performance appraisal module is included.
- Lists paginate at 50 records. Relationship selectors currently cap options at 2,000; very large organizations need server-side autocomplete.
- Database-backed login throttling is basic rate limiting, not a full distributed abuse-prevention service.
- Email commands track successful send time; after a crash between SMTP acceptance and database commit, an email may be resent. A durable outbox/provider delivery-ID integration is a future improvement.

These limits are explicit so the package is not mistaken for a certified production HR product with every possible enterprise module. The implemented core can be run and extended without replacing the architecture.

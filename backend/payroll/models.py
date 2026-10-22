import calendar

from django.conf import settings
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from datetime import date
from types import SimpleNamespace

from core.models import Company, Employee

from .engine import PayInputs, calculate

MONEY = dict(max_digits=12, decimal_places=2, default=0)


class PayrollPeriod(models.Model):
    OPEN, SUBMITTED, PROCESSED, APPROVED, LOCKED = "open", "submitted", "processed", "approved", "locked"
    STATUS_CHOICES = [
        (OPEN, "Open – client entering inputs"),
        (SUBMITTED, "Submitted by client"),
        (PROCESSED, "Processed by Jay's HR"),
        (APPROVED, "Approved by client"),
        (LOCKED, "Locked / paid"),
    ]

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="payroll_periods")
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)
    company_snapshot = models.JSONField(default=dict, blank=True)
    policy_snapshot = models.JSONField(default=dict, blank=True)
    payment_status = models.CharField(max_length=20, default="unpaid")
    payment_reference = models.CharField(max_length=160, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    statutory_reference = models.CharField(max_length=160, blank=True)
    revision = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    copied_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Month whose inputs were carried into this one",
    )

    class Meta:
        ordering = ["-year", "-month"]
        unique_together = [("company", "year", "month")]

    def __str__(self):
        return f"{self.company.code} {self.label}"

    @property
    def label(self):
        return f"{calendar.month_name[self.month]} {self.year}"

    @property
    def client_can_edit(self):
        return self.status == self.OPEN

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and old.status == self.LOCKED:
                allowed = {"payment_status", "payment_reference", "paid_at", "statutory_reference"}
                for f in self._meta.concrete_fields:
                    if f.name not in allowed and getattr(old, f.attname) != getattr(self, f.attname):
                        raise ValidationError("Locked payroll cannot be changed. Use an adjustment in a new month.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.OPEN: raise ValidationError("Only open payroll can be deleted")
        return super().delete(*args, **kwargs)

    @property
    def frozen_company(self):
        import copy
        company = copy.copy(self.company)
        for field, value in self.company_snapshot.items(): setattr(company, field, value)
        return company

    def previous(self):
        """The most recent earlier month for this company."""
        return (PayrollPeriod.objects.filter(company=self.company)
                .filter(models.Q(year__lt=self.year) | models.Q(year=self.year, month__lt=self.month))
                .order_by("-year", "-month").first())


class PayrollInput(models.Model):
    """What the client enters each month for one employee."""

    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="inputs")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    no_pay_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    ot_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    bonus = models.DecimalField(**MONEY)
    epf_earnings = models.DecimalField("EPF-able earnings", **MONEY,
                                       help_text="Commission, piece rate, holiday pay – counted for EPF/ETF")
    other_earnings = models.DecimalField(**MONEY)
    salary_advance = models.DecimalField(**MONEY)
    welfare = models.DecimalField(**MONEY)
    loan_recovery = models.DecimalField(**MONEY)
    other_deductions = models.DecimalField(**MONEY)
    apit_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_template = models.JSONField(default=dict, blank=True)
    tax_note = models.CharField(max_length=255, blank=True)
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("period", "employee")]
        ordering = ["employee__emp_no"]

    def clean(self):
        if self.period_id and self.employee_id and self.period.company_id != self.employee.company_id:
            raise ValidationError("Employee and payroll company must match")
        for f in self._meta.fields:
            if isinstance(f, models.DecimalField):
                value = getattr(self, f.name)
                if value is not None and (not Decimal(value).is_finite() or value < 0):
                    raise ValidationError({f.name: "Must be non-negative"})
        if self.period_id and self.no_pay_days > self.period.company.no_pay_divisor:
            raise ValidationError({"no_pay_days": "Exceeds the payroll divisor"})
        if self.apit_override is not None and not self.tax_note:
            raise ValidationError({"tax_note": "Explain and reference this tax override"})

    def save(self, *args, **kwargs):
        if self.period_id and PayrollPeriod.objects.get(pk=self.period_id).status != PayrollPeriod.OPEN:
            raise ValidationError("Reopen payroll before changing inputs")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.period.status != PayrollPeriod.OPEN: raise ValidationError("Reopen payroll first")
        return super().delete(*args, **kwargs)


INPUT_FIELDS = ["no_pay_days", "ot_hours", "bonus", "epf_earnings", "other_earnings", "salary_advance", "welfare",
                "loan_recovery", "other_deductions", "remarks"]


def copy_inputs(period, source):
    """Copy every employee's monthly inputs from `source` into `period` (overwrites). Returns rows copied."""
    prev = {i.employee_id: i for i in source.inputs.all()}
    n = 0
    for emp in eligible_employees(period.company, period.year, period.month):
        inp, _ = PayrollInput.objects.get_or_create(period=period, employee=emp)
        old = prev.get(emp.id)
        if old:
            for f in ["welfare"]:
                setattr(inp, f, getattr(old, f))
            inp.save()
            n += 1
    period.copied_from = source
    period.save(update_fields=["copied_from"])
    return n


@transaction.atomic
def start_period(company, year, month, carry_forward=True):
    """Open a payroll month. By default last month's inputs are carried forward so the client
    only changes what is different."""
    if not 1 <= int(month) <= 12 or not 2000 <= int(year) <= 2200:
        raise ValidationError("Enter a valid year and month")
    period, created = PayrollPeriod.objects.get_or_create(company=company, year=year, month=month)
    if created:
        for emp in eligible_employees(company, year, month):
            PayrollInput.objects.get_or_create(period=period, employee=emp)
        prev = period.previous()
        if carry_forward and prev:
            copy_inputs(period, prev)
    return period, created


class Payslip(models.Model):
    """Calculated result, frozen once the period is processed."""

    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payslips")
    basic_salary = models.DecimalField(**MONEY)
    fixed_allowance = models.DecimalField(**MONEY)
    epf_allowance = models.DecimalField(**MONEY)
    epf_earnings = models.DecimalField(**MONEY)
    no_pay_deduction = models.DecimalField(**MONEY)
    basic_earned = models.DecimalField(**MONEY)
    ot_amount = models.DecimalField(**MONEY)
    bonus = models.DecimalField(**MONEY)
    other_earnings = models.DecimalField(**MONEY)
    gross_salary = models.DecimalField(**MONEY)
    epf_base = models.DecimalField(**MONEY)
    epf_employee = models.DecimalField(**MONEY)
    epf_employer = models.DecimalField(**MONEY)
    etf_employer = models.DecimalField(**MONEY)
    apit = models.DecimalField(**MONEY)
    salary_advance = models.DecimalField(**MONEY)
    welfare = models.DecimalField(**MONEY)
    loan_recovery = models.DecimalField(**MONEY)
    other_deductions = models.DecimalField(**MONEY)
    total_deductions = models.DecimalField(**MONEY)
    net_salary = models.DecimalField(**MONEY)
    employer_cost = models.DecimalField(**MONEY)
    notes = models.CharField(max_length=255, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("period", "employee")]
        ordering = ["employee__emp_no"]

    def save(self, *args, **kwargs):
        if self.period_id and PayrollPeriod.objects.get(pk=self.period_id).status in (PayrollPeriod.APPROVED, PayrollPeriod.LOCKED):
            if self.pk and set(kwargs.get("update_fields") or []) == {"emailed_at"}: pass
            else: raise ValidationError("Approved payslips are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.period.status in (PayrollPeriod.APPROVED, PayrollPeriod.LOCKED):
            raise ValidationError("Approved payslips are immutable")
        return super().delete(*args, **kwargs)

    @property
    def frozen_employee(self):
        if not self.snapshot: return self.employee
        d = dict(self.snapshot)
        for k in ("join_date", "leave_date"):
            d[k] = date.fromisoformat(d[k]) if d.get(k) else None
        d["epf_name"] = lambda: (self.snapshot.get("surname", ""), self.snapshot.get("initials", ""))
        return SimpleNamespace(**d)


def eligible_employees(company, year, month):
    first, last = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    return company.employees.filter(models.Q(join_date__isnull=True) | models.Q(join_date__lte=last)).filter(
        models.Q(leave_date__isnull=True) | models.Q(leave_date__gte=first)).exclude(status=Employee.RESIGNED, leave_date__isnull=True)


def effective_salary(emp, first, last):
    """Daily weighted salary changes; actual calendar-day joining/leaving proration."""
    from datetime import timedelta
    history = list(emp.salary_history.order_by("effective_date", "id"))
    totals = [Decimal(0), Decimal(0), Decimal(0)]
    day = first
    while day <= last:
        if (not emp.join_date or day >= emp.join_date) and (not emp.leave_date or day <= emp.leave_date):
            applicable = [h for h in history if h.effective_date <= day]
            source = applicable[-1] if applicable else (history[0] if history else emp)
            for i, f in enumerate(("basic_salary", "epf_allowance", "fixed_allowance")): totals[i] += getattr(source, f)
        day += timedelta(days=1)
    return [v / Decimal((last-first).days+1) for v in totals]


def pay_inputs(emp, inp, company):
    """Build engine inputs from an employee record and that month's inputs."""
    first = date(inp.period.year, inp.period.month, 1)
    last = date(inp.period.year, inp.period.month, calendar.monthrange(inp.period.year, inp.period.month)[1])
    basic, allowance, fixed = effective_salary(emp, first, last)
    if inp.salary_template:
        basic=Decimal(inp.salary_template["basic_salary"])
        allowance=sum((Decimal(a["amount"]) for a in inp.salary_template["allowances"] if a["epf"]),Decimal(0))
        fixed=sum((Decimal(a["amount"]) for a in inp.salary_template["allowances"] if not a["epf"]),Decimal(0))
    return PayInputs(
        basic_salary=basic, fixed_allowance=fixed, epf_allowance=allowance, template_rounding=bool(inp.salary_template),
        etf_allowance=sum((Decimal(a["amount"]) for a in inp.salary_template["allowances"] if a.get("etf",a["epf"])),Decimal(0)) if inp.salary_template else None,
        epf_earnings=inp.epf_earnings, no_pay_days=inp.no_pay_days, ot_hours=inp.ot_hours, bonus=inp.bonus,
        other_earnings=inp.other_earnings, salary_advance=inp.salary_advance, welfare=inp.welfare,
        loan_recovery=inp.loan_recovery, other_deductions=inp.other_deductions,
        epf_eligible=emp.epf_eligible, apit_applicable=emp.apit_applicable,
        no_pay_divisor=company.no_pay_divisor, ot_hourly_divisor=company.ot_hourly_divisor,
        ot_multiplier=company.ot_multiplier,
    )


@transaction.atomic
def run_payroll(period: PayrollPeriod):
    from workforce.models import PayrollPolicy, Loan
    from .engine import money
    period = PayrollPeriod.objects.select_for_update().get(pk=period.pk)
    if period.status not in (period.OPEN, period.SUBMITTED, period.PROCESSED):
        raise ValidationError("Payroll must be open or submitted for processing")
    company = period.company
    if company.no_pay_divisor <= 0 or company.ot_hourly_divisor <= 0:
        raise ValidationError("Payroll divisors must be positive")
    first = date(period.year, period.month, 1)
    last = date(period.year, period.month, calendar.monthrange(period.year, period.month)[1])
    policy = PayrollPolicy.objects.filter(company=company, effective_date__lte=first).first()
    if not policy or not policy.reviewed:
        raise ValidationError("Create and review a payroll policy effective on or before this month")
    period.company_snapshot = {f: getattr(company, f) for f in ("name", "code", "address", "email", "phone", "epf_zone", "epf_employer_no", "epf_district_office", "etf_reg_no", "tin", "epf_reg_no", "no_pay_divisor")}
    period.policy_snapshot = {"id": policy.pk, "name": policy.name, "effective_date": str(policy.effective_date), "source_note": policy.source_note,
        "employee_epf": str(policy.employee_epf), "employer_epf": str(policy.employer_epf), "employer_etf": str(policy.employer_etf),
        "annual_relief": str(policy.annual_relief), "bands": policy.bands}
    results = []
    employees = eligible_employees(company, period.year, period.month).select_for_update()
    for emp in employees:
        inp = PayrollInput.objects.filter(period=period, employee=emp).first()
        if not inp:
            if period.status == period.OPEN: inp = PayrollInput.objects.create(period=period, employee=emp)
            else: raise ValidationError(f"Reopen and save inputs for {emp.full_name} first")
        inp.full_clean()
        r = calculate(pay_inputs(emp, inp, company))
        if emp.epf_eligible:
            r.epf_employee = money(r.epf_base * policy.employee_epf)
            r.epf_employer = money(r.epf_base * policy.employer_epf)
            etf_base=r.epf_base
            if inp.salary_template:
                t=inp.salary_template
                etf_base=money((Decimal(t['basic_salary'])+sum((Decimal(a['amount']) for a in t['allowances'] if a.get('etf',a['epf'])),Decimal(0)))*(1-inp.no_pay_days/Decimal(company.no_pay_divisor)))
            r.etf_employer = money(etf_base * policy.employer_etf)
        if emp.apit_applicable:
            if (inp.bonus or inp.other_earnings) and inp.apit_override is None:
                raise ValidationError(f"{emp.full_name}: enter a reviewed APIT override and note for bonus/other earnings")
            remaining = max(Decimal(0), r.gross_salary * 12 - policy.annual_relief)
            tax = Decimal(0)
            for width, rate in policy.bands:
                portion = remaining if width is None else min(remaining, Decimal(str(width)))
                tax += portion * Decimal(str(rate)); remaining -= portion
                if remaining <= 0: break
            r.apit = money(inp.apit_override if inp.apit_override is not None else tax / 12)
        deductions = []
        for loan in Loan.objects.select_for_update().filter(employee=emp, status="approved", start_date__lte=last):
            amount = min(loan.balance, loan.installment)
            if amount > 0: deductions.append({"id": loan.pk, "amount": str(amount)})
        automatic = sum((Decimal(d["amount"]) for d in deductions), Decimal(0))
        r.loan_recovery += automatic
        r.total_deductions = money(r.epf_employee+r.apit+r.salary_advance+r.welfare+r.loan_recovery+r.other_deductions)
        r.net_salary = money(r.gross_salary-r.total_deductions)
        r.employer_cost = money(r.gross_salary+r.epf_employer+r.etf_employer)
        if r.net_salary < 0: raise ValidationError(f"{emp.full_name}: deductions exceed earnings")
        snapshot = {f: str(getattr(emp, f) or "") for f in ("emp_no", "full_name", "designation", "nic", "email", "bank_name", "bank_branch", "bank_account", "bank_account_name", "epf_no", "epf_occupation_grade", "join_date", "leave_date")}
        snapshot["salary_template"]={**inp.salary_template,"monthly_inputs":{k:str(getattr(inp,k)) for k in INPUT_FIELDS}} if inp.salary_template else {}
        snapshot.update(surname=emp.epf_name()[0], initials=emp.epf_name()[1], epf_eligible=emp.epf_eligible,
                        days=str(max(Decimal(0), Decimal(company.no_pay_divisor)-inp.no_pay_days)), loan_deductions=deductions)
        data = r.as_dict(); data["notes"] = "; ".join(data["notes"]); data["snapshot"] = snapshot
        slip, _ = Payslip.objects.update_or_create(period=period, employee=emp, defaults=data)
        results.append(slip)
    period.payslips.exclude(employee__in=employees).delete()
    period.revision += 1
    period.save(update_fields=["company_snapshot", "policy_snapshot", "revision"])
    return results

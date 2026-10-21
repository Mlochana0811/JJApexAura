"""Payroll calculations for Sri Lanka.

EPF / ETF earnings base (EPF Act "total earnings", see epf.lk FAQ):
  * INCLUDED: basic salary, EPF-able allowances (COLA, special living, food allowance,
    holiday pay) and other EPF-able earnings (commission, piece rate).
  * EXCLUDED: overtime, bonus / incentives, reimbursable travel and other non-EPF allowances.
  * No-pay days reduce the EPF base in proportion.

APIT uses the resident-employee rates effective 1 April 2025:
  monthly tax-free relief Rs. 150,000, then 6%, 18%, 24%, 30% on successive
  bands and 36% on the balance. Check against the IRD's published APIT tables
  each year — they can change with the budget.
"""

from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal

TWO = Decimal("0.01")

EPF_EMPLOYEE_RATE = Decimal("0.08")
EPF_EMPLOYER_RATE = Decimal("0.12")
ETF_EMPLOYER_RATE = Decimal("0.03")

# Annual bands (Rs.) from 1 April 2025: (band width, rate). None = unlimited.
APIT_ANNUAL_RELIEF = Decimal("1800000")
APIT_BANDS = [
    (Decimal("1000000"), Decimal("0.06")),
    (Decimal("500000"), Decimal("0.18")),
    (Decimal("500000"), Decimal("0.24")),
    (Decimal("500000"), Decimal("0.30")),
    (None, Decimal("0.36")),
]


def money(x) -> Decimal:
    return Decimal(x).quantize(TWO, rounding=ROUND_HALF_UP)


def monthly_apit(monthly_taxable: Decimal) -> Decimal:
    """APIT for one month on regular monthly employment income."""
    annual = Decimal(monthly_taxable) * 12 - APIT_ANNUAL_RELIEF
    if annual <= 0:
        return Decimal("0.00")
    tax = Decimal(0)
    for width, rate in APIT_BANDS:
        portion = annual if width is None else min(annual, width)
        tax += portion * rate
        annual -= portion
        if annual <= 0:
            break
    return money(tax / 12)


@dataclass
class PayInputs:
    basic_salary: Decimal
    template_rounding: bool = False
    fixed_allowance: Decimal = Decimal(0)      # NOT counted for EPF/ETF
    epf_allowance: Decimal = Decimal(0)        # counted for EPF/ETF (COLA, food, special living …)
    epf_earnings: Decimal = Decimal(0)         # this month's EPF-able extras (commission, piece rate …)
    no_pay_days: Decimal = Decimal(0)
    ot_hours: Decimal = Decimal(0)
    bonus: Decimal = Decimal(0)
    other_earnings: Decimal = Decimal(0)
    salary_advance: Decimal = Decimal(0)
    welfare: Decimal = Decimal(0)
    loan_recovery: Decimal = Decimal(0)
    other_deductions: Decimal = Decimal(0)
    epf_eligible: bool = True
    apit_applicable: bool = True
    no_pay_divisor: int = 30
    ot_hourly_divisor: int = 240
    ot_multiplier: Decimal = Decimal("1.5")


@dataclass
class PayResult:
    basic_salary: Decimal
    fixed_allowance: Decimal
    epf_allowance: Decimal
    epf_earnings: Decimal
    no_pay_deduction: Decimal
    basic_earned: Decimal
    ot_amount: Decimal
    bonus: Decimal
    other_earnings: Decimal
    gross_salary: Decimal
    epf_base: Decimal
    epf_employee: Decimal
    epf_employer: Decimal
    etf_employer: Decimal
    apit: Decimal
    salary_advance: Decimal
    welfare: Decimal
    loan_recovery: Decimal
    other_deductions: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    employer_cost: Decimal
    notes: list = field(default_factory=list)

    def as_dict(self):
        return asdict(self)


def calculate(p: PayInputs) -> PayResult:
    from dataclasses import fields
    for f in fields(p):
        v = getattr(p, f.name)
        if isinstance(v, bool): continue
        try:
            d = Decimal(str(v))
            if not d.is_finite() or d < 0: raise ValueError()
        except Exception:
            raise ValueError(f"{f.name} must be a finite non-negative number")
    if p.no_pay_divisor <= 0 or p.ot_hourly_divisor <= 0:
        raise ValueError("Payroll divisors must be greater than zero")
    if p.no_pay_days > p.no_pay_divisor:
        raise ValueError("No-pay days exceed the configured pay period")
    D = lambda v: Decimal(str(v or 0))  # noqa: E731
    basic, allowance = D(p.basic_salary), D(p.fixed_allowance)
    epf_allow, epf_earn = D(p.epf_allowance), D(p.epf_earnings)
    notes = []

    # No-pay: one day's pay = (basic + all fixed allowances) / divisor
    no_pay_days = D(p.no_pay_days)
    basic_np = money(basic / p.no_pay_divisor * no_pay_days)
    epf_allow_np = money(epf_allow / p.no_pay_divisor * no_pay_days)
    allow_np = money(allowance / p.no_pay_divisor * no_pay_days)
    no_pay = basic_np + epf_allow_np + allow_np
    basic_earned = max(basic - basic_np, Decimal(0))
    epf_allow_earned = max(epf_allow - epf_allow_np, Decimal(0))

    ot = money(basic / p.ot_hourly_divisor * D(p.ot_multiplier) * D(p.ot_hours))
    bonus, other_earn = D(p.bonus), D(p.other_earnings)
    gross = money(basic + epf_allow + allowance - no_pay + ot + bonus + other_earn + epf_earn)

    if p.template_rounding:
        fraction=no_pay_days / D(p.no_pay_divisor)
        gross=money((basic+epf_allow+allowance)*(1-fraction)+basic/D(p.ot_hourly_divisor)*D(p.ot_multiplier)*D(p.ot_hours)+bonus+other_earn+epf_earn)
        no_pay=money(basic+epf_allow+allowance+ot+bonus+other_earn+epf_earn-gross)

    # EPF / ETF — on total earnings: basic + EPF-able allowances + EPF-able extras (never OT or bonus)
    if p.epf_eligible:
        epf_base = money((basic+epf_allow)*(1-no_pay_days/D(p.no_pay_divisor))+epf_earn) if p.template_rounding else money(basic_earned + epf_allow_earned + epf_earn)
        epf_ee = money(epf_base * EPF_EMPLOYEE_RATE)
        epf_er = money(epf_base * EPF_EMPLOYER_RATE)
        etf_er = money(epf_base * ETF_EMPLOYER_RATE)
    else:
        epf_base = epf_ee = epf_er = etf_er = Decimal("0.00")
        notes.append("Not registered for EPF/ETF")

    apit = monthly_apit(gross) if p.apit_applicable else Decimal("0.00")

    adv, welfare, loan, other_ded = D(p.salary_advance), D(p.welfare), D(p.loan_recovery), D(p.other_deductions)
    total_ded = money(epf_ee + apit + adv + welfare + loan + other_ded)
    net = money(gross - total_ded)
    if net < 0:
        notes.append("Deductions exceed earnings — net pay is negative")

    return PayResult(
        basic_salary=money(basic), fixed_allowance=money(allowance), epf_allowance=money(epf_allow),
        epf_earnings=money(epf_earn), no_pay_deduction=money(no_pay),
        basic_earned=money(basic_earned), ot_amount=ot, bonus=money(bonus), other_earnings=money(other_earn),
        gross_salary=gross, epf_base=epf_base, epf_employee=epf_ee, epf_employer=epf_er, etf_employer=etf_er,
        apit=apit, salary_advance=money(adv), welfare=money(welfare), loan_recovery=money(loan),
        other_deductions=money(other_ded), total_deductions=total_ded, net_salary=net,
        employer_cost=money(gross + epf_er + etf_er), notes=notes,
    )

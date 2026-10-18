from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.access import get_company, roles_required
from core.models import Employee

from .models import eligible_employees, PayrollInput, PayrollPeriod, Payslip, copy_inputs, run_payroll, start_period

InputFormSet = forms.modelformset_factory(
    PayrollInput,
    fields=["no_pay_days", "ot_hours", "bonus", "epf_earnings", "other_earnings", "salary_advance", "welfare",
            "loan_recovery", "other_deductions", "remarks"],
    extra=0,
)

TOTAL_FIELDS = ["gross_salary", "epf_base", "epf_employee", "epf_employer", "etf_employer", "apit", "total_deductions",
                "net_salary", "employer_cost"]


@login_required
@roles_required("client_hr")
def period_list(request, company_id):
    company = get_company(request.user, company_id)
    if request.method == "POST":
        y, m = int(request.POST["year"]), int(request.POST["month"])
        p, created = start_period(company, y, m, carry_forward=bool(request.POST.get("carry_forward")))
        return redirect("period_detail", pk=p.pk)
    t = date.today()
    return render(request, "payroll/period_list.html", {
        "company": company, "periods": company.payroll_periods.all(),
        "year": t.year, "month": t.month, "months": range(1, 13),
    })


def _period_for(user, pk):
    p = get_object_or_404(PayrollPeriod.objects.select_related("company"), pk=pk)
    get_company(user, p.company_id)
    return p


@login_required
@roles_required("client_hr")
@transaction.atomic
def period_detail(request, pk):
    p = _period_for(request.user, pk)
    p = PayrollPeriod.objects.select_for_update().get(pk=p.pk)
    # Make sure every active employee has an input row
    if p.status == p.OPEN:
        for emp in eligible_employees(p.company, p.year, p.month):
            PayrollInput.objects.get_or_create(period=p, employee=emp)
    editable = p.client_can_edit
    qs = p.inputs.select_related("employee")
    formset = InputFormSet(request.POST or None, queryset=qs)
    if request.method == "POST":
        if not editable:
            raise PermissionDenied
        if formset.is_valid():
            formset.save()
            messages.success(request, "Monthly inputs saved.")
            return redirect("period_detail", pk=p.pk)
    slips = p.payslips.select_related("employee")
    totals = slips.aggregate(**{f: Sum(f) for f in TOTAL_FIELDS}) if slips else None
    return render(request, "payroll/period_detail.html", {
        "p": p, "formset": formset, "editable": editable, "slips": slips, "totals": totals,
        "previous": p.previous(),
    })


@login_required
@require_POST
@roles_required("client_hr")
def period_action(request, pk, action):
    from workforce.services import payroll_action
    from django.core.exceptions import ValidationError
    try:
        payroll_action(request.user, pk, action, request.POST)
        messages.success(request, "Payroll updated.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("period_detail", pk=pk)


@login_required
def payslip_view(request, pk):
    slip = get_object_or_404(Payslip.objects.select_related("period", "employee", "period__company"), pk=pk)
    u = request.user
    if u.is_employee:
        if slip.employee_id != u.employee_id or slip.period.status not in (PayrollPeriod.APPROVED, PayrollPeriod.LOCKED):
            raise PermissionDenied
    else:
        get_company(u, slip.period.company_id)
    return render(request, "payroll/payslip.html", {
        "s": slip, "p": slip.period, "e": slip.frozen_employee, "c": slip.period.frozen_company,
        "theme": slip.period.company.theme(),
    })


@login_required
def my_payslips(request):
    emp = request.user.employee
    if not emp:
        raise PermissionDenied
    slips = emp.payslips.filter(period__status__in=[PayrollPeriod.APPROVED, PayrollPeriod.LOCKED]).select_related("period")
    return render(request, "payroll/my_payslips.html", {"slips": slips})


from django.http import Http404, HttpResponse  # noqa: E402

from . import exports  # noqa: E402


@login_required
@roles_required("client_hr")
def period_export(request, pk, fmt):
    """Download the month's salary sheet as Excel or PDF (draft if not processed yet)."""
    p = _period_for(request.user, pk)
    if fmt == "xlsx":
        data, ctype = exports.to_excel(p), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fmt == "pdf":
        data, ctype = exports.to_pdf(p), "application/pdf"
    else:
        raise Http404
    resp = HttpResponse(data, content_type=ctype)
    resp["Content-Disposition"] = f'attachment; filename="{exports.filename(p, fmt)}"'
    return resp


from datetime import datetime as _dt  # noqa: E402

from . import statutory  # noqa: E402


def _payment_args(request):
    try:
        pay_date = _dt.strptime(request.GET.get("pay_date", ""), "%Y-%m-%d").date()
    except ValueError:
        pay_date = None
    try:
        submission = max(1, min(99, int(request.GET.get("submission", 1))))
    except ValueError:
        submission = 1
    return {"submission": submission, "pay_mode": request.GET.get("pay_mode", "4"),
            "pay_ref": request.GET.get("pay_ref", ""), "pay_date": pay_date}


@login_required
@roles_required("client_hr")
def period_statutory(request, pk):
    """EPF e-return, Form C details and ETF schedules for one month."""
    p = _period_for(request.user, pk)
    mems = statutory.members(p)
    tot = {k: sum((getattr(m, k) for m in mems), 0) for k in ("earnings", "employee", "employer", "total", "etf")}
    return render(request, "payroll/statutory.html", {
        "p": p, "members": mems, "tot": tot, "issues": statutory.problems(p, mems),
        "pay_modes": statutory.PAY_MODES, "today": date.today(),
    })


@login_required
@roles_required("client_hr")
def period_statutory_file(request, pk, what):
    p = _period_for(request.user, pk)
    if p.status not in (p.APPROVED, p.LOCKED) or not p.payslips.exists():
        messages.error(request, "Approve payroll first – statutory downloads use approved figures.")
        return redirect("period_statutory", pk=p.pk)
    issues = statutory.problems(p)
    if issues:
        messages.error(request, "; ".join(issues))
        return redirect("period_statutory", pk=p.pk)
    kw = _payment_args(request)
    xlsx = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    files = {
        "epf-return": (lambda: statutory.epf_zip(p, **kw), "application/zip",
                       f"EPF e-Return {p.company.name} {statutory.period_code(p)}.zip"),
        "epf-excel": (lambda: statutory.epf_excel(p, kw["submission"]), xlsx,
                      statutory.filename(p, "EPF contribution detail", "xlsx")),
        "form-c": (lambda: statutory.form_c_pdf(p, kw["pay_mode"], kw["pay_ref"], kw["pay_date"]), "application/pdf",
                   statutory.filename(p, "EPF Form C details", "pdf")),
        "etf-pdf": (lambda: statutory.etf_pdf(p), "application/pdf", statutory.filename(p, "ETF contributions", "pdf")),
        "etf-excel": (lambda: statutory.etf_excel(p), xlsx, statutory.filename(p, "ETF contributions", "xlsx")),
    }
    if what not in files:
        raise Http404
    make, ctype, name = files[what]
    resp = HttpResponse(make(), content_type=ctype)
    resp["Content-Disposition"] = f'attachment; filename="{name}"'
    return resp


@login_required
@roles_required("client_hr")
def etf_half_year(request, company_id):
    company = get_company(request.user, company_id)
    try:
        year, half = int(request.GET["year"]), int(request.GET["half"])
        assert half in (1, 2)
    except (KeyError, ValueError, AssertionError):
        raise Http404
    resp = HttpResponse(statutory.etf_half_year_excel(company, year, half),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="ETF half-year {year} H{half} - {company.name}.xlsx"'
    return resp

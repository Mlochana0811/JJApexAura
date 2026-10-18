from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render

from leave.models import HRRequest, LeaveRequest, leave_balances
from payroll.models import PayrollPeriod

from .access import get_employee, roles_required, visible_employees
from .forms import EmployeeForm
from .models import Company, Employee, SalaryHistory


@login_required
def dashboard(request):
    u = request.user
    today = date.today()
    if u.is_employee:
        emp = u.employee
        if not emp:
            messages.error(request, "Your login is not linked to an employee record. Please contact HR.")
            return render(request, "core/dashboard_employee.html", {})
        return render(request, "core/dashboard_employee.html", {
            "emp": emp,
            "balances": leave_balances(emp, today.year),
            "leaves": emp.leave_requests.all()[:5],
            "requests": emp.hr_requests.all()[:5],
            "payslips": emp.payslips.filter(period__status__in=[PayrollPeriod.APPROVED, PayrollPeriod.LOCKED])
                        .select_related("period")[:6],
        })

    companies = u.companies().annotate(
        active=Count("employees", filter=Q(employees__status=Employee.ACTIVE))
    )
    employees = visible_employees(u).filter(status=Employee.ACTIVE)
    company_rows = []
    for c in companies:
        period = PayrollPeriod.objects.filter(company=c, year=today.year, month=today.month).first()
        gaps = sum(1 for e in employees if e.company_id == c.id and e.missing_fields)
        company_rows.append({"company": c, "period": period, "gaps": gaps})
    scope = Q(employee__in=employees)
    return render(request, "core/dashboard_hr.html", {
        "company_rows": company_rows,
        "pending_leave": LeaveRequest.objects.filter(scope, status=LeaveRequest.PENDING).select_related("employee", "leave_type"),
        "open_requests": HRRequest.objects.filter(scope, status__in=[HRRequest.OPEN, HRRequest.IN_PROGRESS]).select_related("employee"),
        "headcount": employees.count(),
        "today": today,
    })


@login_required
@roles_required("client_hr")
def employee_list(request):
    qs = visible_employees(request.user)
    company_id = request.GET.get("company")
    if company_id:
        qs = qs.filter(company_id=company_id)
    status = request.GET.get("status", "active")
    if status != "all":
        qs = qs.filter(status=status)
    q = request.GET.get("q")
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(nic__icontains=q) | Q(emp_no__icontains=q))
    return render(request, "core/employee_list.html", {
        "employees": qs, "companies": request.user.companies(),
        "company_id": company_id, "status": status, "q": q or "",
    })


@login_required
def employee_detail(request, pk):
    if request.user.role == "manager":
        return redirect("/app/employees")
    emp = get_employee(request.user, pk)
    return render(request, "core/employee_detail.html", {
        "emp": emp,
        "balances": leave_balances(emp, date.today().year),
        "history": emp.salary_history.all(),
        "payslips": emp.payslips.select_related("period")[:12],
    })


@login_required
@roles_required("client_hr")
def employee_edit(request, pk=None):
    return redirect("/app/employees")

def _retired_employee_edit(request, pk=None):
    emp = get_employee(request.user, pk) if pk else None
    old = (emp.basic_salary, emp.epf_allowance, emp.fixed_allowance) if emp else None
    form = EmployeeForm(request.POST or None, instance=emp, user=request.user)
    if request.method == "POST" and form.is_valid():
        e = form.save()
        if old != (e.basic_salary, e.epf_allowance, e.fixed_allowance):
            SalaryHistory.objects.create(
                employee=e, effective_date=date.today(), basic_salary=e.basic_salary,
                epf_allowance=e.epf_allowance, fixed_allowance=e.fixed_allowance, reason="New employee" if not old else "Salary updated",
            )
        messages.success(request, f"Saved {e.full_name}.")
        return redirect("employee_detail", pk=e.pk)
    return render(request, "core/employee_form.html", {"form": form, "emp": emp})


@login_required
@roles_required()
def company_list(request):
    return render(request, "core/company_list.html", {"companies": Company.objects.all()})


from django.contrib.auth.views import PasswordChangeView  # noqa: E402


class FirstPasswordChangeView(PasswordChangeView):
    template_name = "auth/password.html"
    success_url = "/"

    def form_valid(self, form):
        resp = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save(update_fields=["must_change_password"])
        messages.success(self.request, "Password updated.")
        return resp


from .branding import DEFAULT_ACCENT, DEFAULT_BRAND, PRESETS, STYLES, palette_from_logo  # noqa: E402
from .forms import BrandingForm, SiteThemeForm  # noqa: E402
from .models import SiteTheme  # noqa: E402


def _site_branding(request):
    site = SiteTheme.objects.first() or SiteTheme.objects.create()
    form = SiteThemeForm(request.POST or None, instance=site)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Jay's HR default look saved.")
        return redirect("/branding/?company=site")
    return render(request, "core/branding.html", {
        "form": form, "site_mode": True, "presets": PRESETS, "styles": STYLES,
        "default_brand": DEFAULT_BRAND, "default_accent": DEFAULT_ACCENT, "preview": site.theme(),
    })


@login_required
@roles_required("client_hr")
def branding(request):
    """Client HR sets their company's logo and colours. Admin can do it for any company (?company=)."""
    u = request.user
    cid = request.GET.get("company") if u.is_hr_admin else u.company_id
    if not cid:
        return render(request, "core/branding_pick.html", {"companies": u.companies(), "site": SiteTheme.current()})
    if cid == "site":
        return _site_branding(request)
    company = Company.objects.get(pk=cid) if u.is_hr_admin else u.company
    had_logo = bool(company.logo)
    form = BrandingForm(request.POST or None, request.FILES or None, instance=company)
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        if request.POST.get("remove_logo"):
            c.logo = None
        new_logo = "logo" in request.FILES
        c.save()
        if new_logo:
            colours = palette_from_logo(c.logo.open("rb"))
            if colours and (not had_logo or not c.brand_color):
                c.brand_color = colours[0]
                c.accent_color = colours[1] if len(colours) > 1 else ""
                c.use_own_theme = True
                c.save()
                messages.success(request, "Logo uploaded – we picked your colours from it. Adjust them below if you like.")
            else:
                messages.success(request, "Logo uploaded.")
        else:
            messages.success(request, "Branding saved.")
        url = "branding" + (f"?company={c.pk}" if u.is_hr_admin else "")
        return redirect("/" + url)
    palette = []
    if company.logo:
        try:
            palette = palette_from_logo(company.logo.open("rb"))
        except Exception:  # unreadable image
            palette = []
    return render(request, "core/branding.html", {
        "form": form, "company": company, "palette": palette, "presets": PRESETS, "styles": STYLES,
        "default_brand": DEFAULT_BRAND, "default_accent": DEFAULT_ACCENT,
        "preview": company.theme(),
    })

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.access import roles_required, visible_employees
from core.forms import HRRequestForm, HRResponseForm, LeaveApplyForm

from .models import HRRequest, LeaveRequest, leave_balances


def _own_employee(request):
    emp = request.user.employee
    if not emp:
        raise PermissionDenied("Your login is not linked to an employee record.")
    return emp


@login_required
def my_leave(request):
    emp = _own_employee(request)
    form = LeaveApplyForm(request.POST or None, employee=emp)
    balances = leave_balances(emp, date.today().year)
    if request.method == "POST" and form.is_valid():
        lr = form.save(commit=False)
        lr.employee = emp
        from workforce.services import submit_leave
        from django.core.exceptions import ValidationError
        try:
            submit_leave(request.user, lr)
            messages.success(request, "Leave request sent to HR.")
            return redirect("my_leave")
        except ValidationError as exc:
            form.add_error(None, "; ".join(exc.messages))
    return render(request, "leave/my_leave.html", {
        "form": form, "balances": balances, "leaves": emp.leave_requests.select_related("leave_type"),
    })


@login_required
@require_POST
def cancel_leave(request, pk):
    lr = get_object_or_404(LeaveRequest, pk=pk, employee=_own_employee(request), status=LeaveRequest.PENDING)
    lr.status = LeaveRequest.CANCELLED
    lr.save()
    messages.info(request, "Leave request cancelled.")
    return redirect("my_leave")


@login_required
@roles_required("client_hr")
def leave_approvals(request):
    emps = visible_employees(request.user)
    if request.method == "POST":
        from workforce.services import decide_leave
        from django.core.exceptions import ValidationError
        try:
            decide_leave(request.user, request.POST["id"], request.POST.get("action"), request.POST.get("comment", ""))
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        return redirect("leave_approvals")
    return render(request, "leave/approvals.html", {
        "pending": LeaveRequest.objects.filter(employee__in=emps, status=LeaveRequest.PENDING)
                   .select_related("employee", "leave_type", "employee__company"),
        "recent": LeaveRequest.objects.filter(employee__in=emps).exclude(status=LeaveRequest.PENDING)
                  .select_related("employee", "leave_type")[:20],
    })


@login_required
def my_requests(request):
    emp = _own_employee(request)
    form = HRRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        r = form.save(commit=False)
        r.employee = emp
        r.save()
        messages.success(request, "Your request has been sent to HR.")
        return redirect("my_requests")
    return render(request, "leave/my_requests.html", {"form": form, "requests": emp.hr_requests.all()})


@login_required
@roles_required("client_hr")
def hr_requests(request):
    emps = visible_employees(request.user)
    qs = HRRequest.objects.filter(employee__in=emps).select_related("employee", "employee__company")
    if request.method == "POST":
        r = get_object_or_404(qs, pk=request.POST["id"])
        form = HRResponseForm(request.POST, instance=r)
        if form.is_valid():
            r = form.save(commit=False)
            r.handled_by = request.user
            r.save()
            messages.success(request, f"Updated request from {r.employee.full_name}.")
        return redirect("hr_requests")
    return render(request, "leave/hr_requests.html", {
        "open": [(r, HRResponseForm(instance=r)) for r in qs.filter(status__in=[HRRequest.OPEN, HRRequest.IN_PROGRESS])],
        "closed": qs.filter(status__in=[HRRequest.DONE, HRRequest.DECLINED])[:20],
    })

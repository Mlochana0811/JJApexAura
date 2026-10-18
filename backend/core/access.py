"""Who can see what. Every view goes through these helpers so a client never sees another client's data."""

from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Company, Employee
from django.db.models import Q


def roles_required(*roles):
    """Allow only the given roles ('admin', 'client_hr', 'employee'). Admins always pass."""

    def deco(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            u = request.user
            if u.is_hr_admin or u.role in roles:
                return view(request, *args, **kwargs)
            raise PermissionDenied
        return wrapper
    return deco


def visible_employees(user):
    qs = Employee.objects.select_related("company")
    if user.is_hr_admin:
        return qs
    if user.is_client_hr:
        return qs.filter(company_id=user.company_id)
    if user.role == "manager":
        return qs.filter(company_id=user.company_id).filter(Q(manager=user) | Q(pk=user.employee_id))
    return qs.filter(pk=user.employee_id)


def get_employee(user, pk):
    return get_object_or_404(visible_employees(user), pk=pk)


def get_company(user, pk):
    if not user.is_hr_admin and user.company_id != int(pk):
        raise PermissionDenied
    return get_object_or_404(Company, pk=pk)


class ScopedCompanyMixin:
    """Limit a form's company dropdown to what the user may use."""

    def limit_company(self, user):
        if "company" in self.fields:
            if user.is_hr_admin:
                self.fields["company"].queryset = Company.objects.filter(is_active=True)
            else:
                self.fields["company"].queryset = Company.objects.filter(pk=user.company_id)
                self.fields["company"].initial = user.company_id

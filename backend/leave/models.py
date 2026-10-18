from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from core.models import Company, Employee

# Defaults based on the Shop & Office Employees Act; each company can edit them.
DEFAULT_LEAVE_TYPES = [
    ("AL", "Annual leave", 14, True),
    ("CL", "Casual leave", 7, True),
    ("ML", "Medical leave", 7, True),
    ("MAT", "Maternity leave", 84, True),
    ("NP", "No-pay leave", 0, False),
]


class LeaveType(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="leave_types")
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=60)
    days_per_year = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    is_paid = models.BooleanField(default=True)
    has_limit = models.BooleanField(default=True, help_text="Untick for leave with no yearly cap")

    class Meta:
        ordering = ["company", "code"]
        unique_together = [("company", "code")]

    def __str__(self):
        return self.name

    @classmethod
    def seed_defaults(cls, company):
        for code, name, days, paid in DEFAULT_LEAVE_TYPES:
            cls.objects.get_or_create(
                company=company, code=code,
                defaults=dict(name=name, days_per_year=days, is_paid=paid, has_limit=code != "NP"),
            )


class LeaveEntitlement(models.Model):
    """Optional per-employee override, e.g. pro-rated leave in the first year."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_entitlements")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    days = models.DecimalField(max_digits=5, decimal_places=1)

    class Meta:
        unique_together = [("employee", "leave_type", "year")]


class LeaveRequest(models.Model):
    PENDING, APPROVED, REJECTED, CANCELLED = "pending", "approved", "rejected", "cancelled"
    STATUS_CHOICES = [
        (PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected"), (CANCELLED, "Cancelled"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    half_day = models.BooleanField(default=False, help_text="Single half day")
    days = models.DecimalField(max_digits=5, decimal_places=1, editable=False, default=0)
    days_by_year = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    hr_comment = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee.full_name}: {self.leave_type} {self.start_date}"

    @staticmethod
    def count_days(start, end, half_day=False):
        """Working days (Mon–Fri) between two dates, inclusive."""
        if half_day:
            return Decimal("0.5")
        days, d = 0, start
        while d <= end:
            if d.weekday() < 5:
                days += 1
            d += timedelta(days=1)
        return Decimal(days)

    def save(self, *args, **kwargs):
        if self.half_day:
            self.end_date = self.start_date
        from workforce.services import leave_allocations
        if not self.pk or not self.days_by_year:
            self.days_by_year = {str(y): str(n) for y,n in leave_allocations(self).items()}
        self.days = sum((Decimal(n) for n in self.days_by_year.values()), Decimal(0))
        super().save(*args, **kwargs)


def leave_balances(employee, year, exclude_id=None):
    """Entitlement, used, pending and remaining days per leave type for one year."""
    rows = []
    overrides = {e.leave_type_id: e.days for e in employee.leave_entitlements.filter(year=year)}
    for lt in LeaveType.objects.filter(company=employee.company):
        reqs = LeaveRequest.objects.filter(employee=employee, leave_type=lt, start_date__year__lte=year, end_date__year__gte=year).exclude(pk=exclude_id)
        from workforce.services import leave_allocations
        used = sum(((Decimal(lr.days_by_year.get(str(year), 0)) if lr.days_by_year else leave_allocations(lr).get(year, Decimal(0))) for lr in reqs.filter(status=LeaveRequest.APPROVED)), Decimal(0))
        pending = sum(((Decimal(lr.days_by_year.get(str(year), 0)) if lr.days_by_year else leave_allocations(lr).get(year, Decimal(0))) for lr in reqs.filter(status=LeaveRequest.PENDING)), Decimal(0))
        entitled = overrides.get(lt.id, lt.days_per_year)
        rows.append({
            "type": lt,
            "entitled": entitled if lt.has_limit else None,
            "used": used,
            "pending": pending,
            "remaining": (entitled - used) if lt.has_limit else None,
        })
    return rows


class HRRequest(models.Model):
    CATEGORY_CHOICES = [
        ("salary_confirmation", "Salary confirmation letter"),
        ("service_letter", "Service / employment letter"),
        ("salary_advance", "Salary advance"),
        ("detail_update", "Update my personal / bank details"),
        ("payslip_query", "Payslip query"),
        ("other", "Other"),
    ]
    OPEN, IN_PROGRESS, DONE, DECLINED = "open", "in_progress", "done", "declined"
    STATUS_CHOICES = [(OPEN, "Open"), (IN_PROGRESS, "In progress"), (DONE, "Completed"), (DECLINED, "Declined")]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="hr_requests")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    subject = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                 help_text="For salary advance requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)
    response = models.TextField(blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "HR request"

    def __str__(self):
        return self.subject

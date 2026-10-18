from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class Company(models.Model):
    """A client company whose payroll Jay's HR runs."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10, unique=True, help_text="Short code, e.g. CG")
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    epf_reg_no = models.CharField("EPF registration no.", max_length=50, blank=True)
    epf_zone = models.CharField("EPF zone code", max_length=1, blank=True, help_text="Letter, e.g. A")
    epf_employer_no = models.CharField("EPF employer no.", max_length=6, blank=True,
                                       help_text="Up to 6 digits – also used for ETF")
    epf_district_office = models.CharField("EPF district office code", max_length=2, blank=True)
    etf_reg_no = models.CharField("ETF registration no.", max_length=50, blank=True)
    tin = models.CharField("Tax identification no. (TIN)", max_length=50, blank=True)
    # Payroll settings
    working_weekdays = models.JSONField(default=list, blank=True, help_text="Empty means Monday to Friday; otherwise integers 0–6")
    payday = models.PositiveSmallIntegerField(default=10)
    no_pay_divisor = models.PositiveIntegerField(
        default=30, help_text="Days used to work out one day's pay for no-pay deductions"
    )
    ot_hourly_divisor = models.PositiveIntegerField(
        default=240, help_text="Basic ÷ this = hourly rate for overtime"
    )
    ot_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.50"))
    payroll_cutoff_day = models.PositiveIntegerField(
        default=25, help_text="Day of the month by which the client must submit inputs"
    )
    # Branding
    logo = models.ImageField(upload_to="logos/", blank=True)
    use_own_theme = models.BooleanField(
        default=False, help_text="Show the portal in this company's colours instead of the Jay's HR default"
    )
    brand_color = models.CharField(max_length=7, blank=True, help_text="Main colour, e.g. #1f6f5c")
    accent_color = models.CharField(max_length=7, blank=True)
    style = models.CharField(max_length=10, default="soft", help_text="Page design")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name

    def theme(self):
        from .branding import theme
        if self.use_own_theme and self.brand_color:
            return theme(self.brand_color, self.accent_color or None, self.style)
        return SiteTheme.current().theme()


class SiteTheme(models.Model):
    """Jay's HR's own look – used for admins, the login page and clients without their own colours."""

    brand_color = models.CharField(max_length=7, default="#4f7462")
    accent_color = models.CharField(max_length=7, default="#b9d0c2")
    style = models.CharField(max_length=10, default="bold")

    @classmethod
    def current(cls):
        obj = cls.objects.first()
        return obj or cls()

    def theme(self):
        from .branding import theme
        return theme(self.brand_color, self.accent_color, self.style)


class Employee(models.Model):
    ACTIVE, RESIGNED, ON_LEAVE = "active", "resigned", "on_leave"
    STATUS_CHOICES = [(ACTIVE, "Active"), (ON_LEAVE, "On long leave"), (RESIGNED, "Resigned / left")]

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="employees")
    emp_no = models.CharField("Employee no.", max_length=20)
    full_name = models.CharField(max_length=200)
    nic = models.CharField("NIC", max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True, help_text="Payslips are emailed here")
    designation = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    join_date = models.DateField(null=True, blank=True)
    leave_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)

    epf_no = models.CharField("EPF member no.", max_length=20, blank=True)
    epf_eligible = models.BooleanField("Contributes to EPF/ETF", default=True)
    apit_applicable = models.BooleanField("APIT applies", default=True)

    bank_name = models.CharField(max_length=100, blank=True)
    bank_branch = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=40, blank=True)

    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    epf_allowance = models.DecimalField(
        "EPF-able allowances", max_digits=12, decimal_places=2, default=0,
        help_text="Counts for EPF/ETF: cost of living, special living, food allowance and similar",
    )
    fixed_allowance = models.DecimalField(
        "Other fixed allowances", max_digits=12, decimal_places=2, default=0,
        help_text="NOT counted for EPF/ETF: e.g. travel reimbursement, performance/incentive allowance",
    )
    surname = models.CharField(max_length=40, blank=True, help_text="As on NIC – used in the EPF return")
    initials = models.CharField(max_length=20, blank=True, help_text="As on NIC – used in the EPF return")
    epf_occupation_grade = models.CharField("EPF occupation grade", max_length=3, blank=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="team")
    emergency_contact = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["company", "emp_no"]
        unique_together = [("company", "emp_no")]

    def __str__(self):
        return f"{self.emp_no} – {self.full_name}"

    @property
    def total_fixed_pay(self):
        return self.basic_salary + self.epf_allowance + self.fixed_allowance

    def epf_name(self):
        """(surname, initials) for the EPF return – stored values, else worked out from the full name."""
        parts = self.full_name.replace(".", " ").split()
        surname = self.surname or (parts[-1] if parts else "")
        initials = self.initials or "".join(p[0] for p in parts[:-1])
        return surname.upper(), initials.upper()

    @property
    def is_active(self):
        return self.status == self.ACTIVE

    @property
    def missing_fields(self):
        """Master-data gaps that need filling before payroll."""
        checks = {
            "NIC": self.nic,
            "Bank account": self.bank_account,
            "Join date": self.join_date,
            "Designation": self.designation,
            "Email": self.email,
        }
        if self.epf_eligible:
            checks["EPF no."] = self.epf_no
        return [k for k, v in checks.items() if not v]


class SalaryHistory(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="salary_history")
    effective_date = models.DateField()
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    epf_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fixed_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date"]
        verbose_name_plural = "salary history"


class User(AbstractUser):
    """Login account. Role decides what the person can see."""

    ADMIN, CLIENT_HR, EMPLOYEE, MANAGER = "admin", "client_hr", "employee", "manager"
    ROLE_CHOICES = [(ADMIN, "Jay's HR admin"), (CLIENT_HR, "Client HR"), (EMPLOYEE, "Employee"), (MANAGER, "Manager")]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=EMPLOYEE)
    company = models.ForeignKey(
        Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="users",
        help_text="Client HR and employees only see this company",
    )
    employee = models.OneToOneField(
        Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="user"
    )
    must_change_password = models.BooleanField(default=True)

    @property
    def is_hr_admin(self):
        return self.role == self.ADMIN or self.is_superuser

    @property
    def is_client_hr(self):
        return self.role == self.CLIENT_HR

    @property
    def is_employee(self):
        return self.role == self.EMPLOYEE

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.role != self.ADMIN and not self.is_superuser and not self.company_id:
            raise ValidationError("Employee, manager and HR accounts require a company")
        if self.employee_id and self.employee.company_id != self.company_id:
            raise ValidationError("Account and employee must belong to the same company")

    def companies(self):
        if self.is_hr_admin:
            return Company.objects.filter(is_active=True)
        return Company.objects.filter(pk=self.company_id)

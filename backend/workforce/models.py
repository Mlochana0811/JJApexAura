from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError

class AuditEvent(models.Model):
    company = models.ForeignKey("core.Company", null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    entity = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at"]

class Holiday(models.Model):
    company = models.ForeignKey("core.Company", on_delete=models.CASCADE)
    date = models.DateField()
    name = models.CharField(max_length=120)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "date"], name="unique_holiday")]

class Shift(models.Model):
    company = models.ForeignKey("core.Company", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    grace_minutes = models.PositiveIntegerField(default=10)
    expected_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    def __str__(self): return self.name

class Roster(models.Model):
    employee = models.ForeignKey("core.Employee", on_delete=models.PROTECT)
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT)
    date = models.DateField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "date"], name="one_roster_per_day")]

class Attendance(models.Model):
    employee = models.ForeignKey("core.Employee", on_delete=models.PROTECT)
    date = models.DateField()
    check_in = models.DateTimeField()
    check_out = models.DateTimeField(null=True, blank=True)
    roster = models.ForeignKey(Roster, null=True, blank=True, on_delete=models.SET_NULL)
    late_minutes = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["-date", "-check_in"]
        constraints = [models.UniqueConstraint(fields=["employee"], condition=models.Q(check_out__isnull=True), name="one_open_attendance")]
    @property
    def worked_hours(self):
        from django.utils import timezone
        end = self.check_out or timezone.now()
        seconds = (end-self.check_in).total_seconds()
        for b in self.breaks.all(): seconds -= ((b.end or end)-b.start).total_seconds()
        return round(max(0, seconds)/3600, 2)

class Break(models.Model):
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name="breaks")
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["attendance"], condition=models.Q(end__isnull=True), name="one_open_break")]

class AttendanceCorrection(models.Model):
    employee = models.ForeignKey("core.Employee", on_delete=models.PROTECT)
    attendance = models.ForeignKey(Attendance, null=True, blank=True, on_delete=models.PROTECT)
    requested_in = models.DateTimeField()
    requested_out = models.DateTimeField()
    reason = models.TextField()
    status = models.CharField(max_length=20, default="pending")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

class Announcement(models.Model):
    company = models.ForeignKey("core.Company", on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    body = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-created_at"]

class Acknowledgement(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["announcement", "user"], name="unique_ack")]

class RequestMessage(models.Model):
    request = models.ForeignKey("leave.HRRequest", on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class Document(models.Model):
    employee = models.ForeignKey("core.Employee", on_delete=models.PROTECT)
    title = models.CharField(max_length=160)
    kind = models.CharField(max_length=40, default="contract")
    file = models.FileField(upload_to="private/documents/%Y/%m/")
    expires_on = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

class Loan(models.Model):
    employee = models.ForeignKey("core.Employee", on_delete=models.PROTECT)
    kind = models.CharField(max_length=20, default="loan")
    principal = models.DecimalField(max_digits=12, decimal_places=2)
    installment = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="pending")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    @property
    def balance(self):
        from django.db.models import Sum
        return self.principal - (self.repayments.aggregate(n=Sum("amount"))["n"] or 0)

class LoanRepayment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="repayments")
    period = models.ForeignKey("payroll.PayrollPeriod", on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["loan", "period"], name="unique_loan_payment")]

class Asset(models.Model):
    company = models.ForeignKey("core.Company", on_delete=models.PROTECT)
    employee = models.ForeignKey("core.Employee", null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=150)
    serial_number = models.CharField(max_length=100)
    issued_on = models.DateField(null=True, blank=True)
    returned_on = models.DateField(null=True, blank=True)
    condition = models.CharField(max_length=100, default="Good")
    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "serial_number"], name="unique_asset_serial")]

class ChecklistItem(models.Model):
    employee = models.ForeignKey("core.Employee", on_delete=models.PROTECT)
    category = models.CharField(max_length=20, default="onboarding")
    title = models.CharField(max_length=160)
    due_date = models.DateField(null=True, blank=True)
    completed = models.BooleanField(default=False)

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.CharField(max_length=250)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-created_at"]

class Invitation(models.Model):
    employee = models.ForeignKey("core.Employee", on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

class PayrollPolicy(models.Model):
    company = models.ForeignKey("core.Company", on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    effective_date = models.DateField()
    employee_epf = models.DecimalField(max_digits=6, decimal_places=4, default="0.08")
    employer_epf = models.DecimalField(max_digits=6, decimal_places=4, default="0.12")
    employer_etf = models.DecimalField(max_digits=6, decimal_places=4, default="0.03")
    annual_relief = models.DecimalField(max_digits=14, decimal_places=2, default="1800000")
    bands = models.JSONField(default=list)
    reviewed = models.BooleanField(default=False)
    source_note = models.TextField(blank=True)
    class Meta: ordering = ["-effective_date", "-id"]

class SalarySheet(models.Model):
    """Versioned manual salary worksheet. Separate from statutory payroll runs."""
    company = models.ForeignKey('core.Company', on_delete=models.PROTECT)
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=12, default='draft', choices=[('draft','Draft'),('finalized','Finalized')])
    rows = models.JSONField(default=list)
    template_config = models.JSONField(default=dict, blank=True)
    company_name = models.CharField(max_length=200)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['company','year','month'], name='unique_salary_sheet_month')]
        ordering = ['-year','-month']

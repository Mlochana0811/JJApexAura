from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from leave.models import HRRequest, LeaveEntitlement, LeaveRequest, LeaveType
from payroll.models import PayrollInput, PayrollPeriod, Payslip

from .models import Company, Employee, SalaryHistory, User

admin.site.site_header = "Jay's HR – Administration"


@admin.register(User)
class JUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Jay's HR", {"fields": ("role", "company", "employee", "must_change_password")}),)
    list_display = ("username", "first_name", "role", "company", "is_active")
    list_filter = ("role", "company")
    def save_model(self, request, obj, form, change):
        from workforce.services import audit, plain
        from django.core.exceptions import ValidationError
        before = plain(User.objects.get(pk=obj.pk)) if change else {}
        before.pop("password", None)
        if obj.employee_id and obj.employee.company_id != obj.company_id:
            raise ValidationError("User company must match employee company")
        super().save_model(request, obj, form, change)
        audit(request.user, "account.admin-edit", obj, before)



@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "epf_reg_no", "is_active")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


class SalaryHistoryInline(admin.TabularInline):
    model = SalaryHistory
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("emp_no", "full_name", "company", "designation", "basic_salary", "status")
    list_filter = ("company", "status", "epf_eligible")
    search_fields = ("full_name", "nic", "emp_no")
    inlines = []
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


class LedgerAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
admin.site.register([PayrollPeriod, PayrollInput, Payslip, LeaveRequest, HRRequest, SalaryHistory], LedgerAdmin)
admin.site.register([LeaveType, LeaveEntitlement], LedgerAdmin)

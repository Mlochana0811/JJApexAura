from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.views.generic import RedirectView

from core import views as core
from leave import views as leave
from payroll import views as payroll

urlpatterns = [
    path("api/", include("workforce.urls")),
    path("admin/", admin.site.urls),
    path("login/", RedirectView.as_view(url="/app/login", permanent=False), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password/", core.FirstPasswordChangeView.as_view(), name="password_change"),

    path("", core.dashboard, name="dashboard"),
    path("companies/", core.company_list, name="company_list"),
    path("branding/", core.branding, name="branding"),
    path("employees/", core.employee_list, name="employee_list"),
    path("employees/new/", core.employee_edit, name="employee_new"),
    path("employees/<int:pk>/", core.employee_detail, name="employee_detail"),
    path("employees/<int:pk>/edit/", core.employee_edit, name="employee_edit"),

    path("leave/", leave.my_leave, name="my_leave"),
    path("leave/<int:pk>/cancel/", leave.cancel_leave, name="cancel_leave"),
    path("leave/approvals/", leave.leave_approvals, name="leave_approvals"),
    path("requests/", leave.my_requests, name="my_requests"),
    path("requests/manage/", leave.hr_requests, name="hr_requests"),

    path("payroll/company/<int:company_id>/", payroll.period_list, name="period_list"),
    path("payroll/<int:pk>/", payroll.period_detail, name="period_detail"),
    path("payroll/<int:pk>/export.<str:fmt>", payroll.period_export, name="period_export"),
    path("payroll/<int:pk>/epf-etf/", payroll.period_statutory, name="period_statutory"),
    path("payroll/<int:pk>/epf-etf/<str:what>/", payroll.period_statutory_file, name="period_statutory_file"),
    path("payroll/company/<int:company_id>/etf-half-year/", payroll.etf_half_year, name="etf_half_year"),
    path("payroll/<int:pk>/<str:action>/", payroll.period_action, name="period_action"),
    path("payslips/", payroll.my_payslips, name="my_payslips"),
    path("payslip/<int:pk>/", payroll.payslip_view, name="payslip"),
]

if settings.DEBUG:
    urlpatterns += static("/media/logos/", document_root=settings.MEDIA_ROOT / "logos")

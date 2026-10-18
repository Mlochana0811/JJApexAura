from workforce.testing import company as test_company
from datetime import date
from decimal import Decimal as D

from django.test import TestCase

from leave.models import HRRequest, LeaveRequest, LeaveType
from payroll.models import PayrollPeriod

from .models import Company, Employee, User


class PortalFlowTests(TestCase):
    def setUp(self):
        self.a = test_company(name="Alpha Ltd", code="AL")
        self.b = test_company(name="Beta Ltd", code="BE")
        for c in (self.a, self.b):
            LeaveType.seed_defaults(c)
        self.ea = Employee.objects.create(company=self.a, emp_no="A1", full_name="Anu", basic_salary=30000,
                                          fixed_allowance=20000)
        self.eb = Employee.objects.create(company=self.b, emp_no="B1", full_name="Bala", basic_salary=30000)

        def user(name, role, company=None, emp=None):
            u = User.objects.create_user(name, password="pw", role=role, company=company, employee=emp)
            u.must_change_password = False
            u.save()
            return u

        self.admin = user("jay", User.ADMIN)
        self.hr_a = user("al.hr", User.CLIENT_HR, self.a)
        self.emp_a = user("a1", User.EMPLOYEE, self.a, self.ea)

    def login(self, u):
        self.client.force_login(u)

    def test_new_login_must_change_password(self):
        u = User.objects.create_user("new", password="pw", role=User.EMPLOYEE)
        self.client.force_login(u)
        self.assertRedirects(self.client.get("/"), "/password/")

    def test_client_hr_sees_only_own_company(self):
        self.login(self.hr_a)
        r = self.client.get("/employees/")
        self.assertContains(r, "Anu")
        self.assertNotContains(r, "Bala")
        self.assertEqual(self.client.get(f"/employees/{self.eb.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/payroll/company/{self.b.pk}/").status_code, 403)

    def test_employee_cannot_open_hr_pages(self):
        self.login(self.emp_a)
        self.assertEqual(self.client.get("/employees/").status_code, 403)
        self.assertEqual(self.client.get("/leave/approvals/").status_code, 403)

    def test_leave_apply_and_approve(self):
        self.login(self.emp_a)
        al = LeaveType.objects.get(company=self.a, code="AL")
        r = self.client.post("/leave/", {"leave_type": al.pk, "start_date": "2026-10-12", "end_date": "2026-10-14",
                                         "reason": "Family"})
        self.assertRedirects(r, "/leave/")
        lr = LeaveRequest.objects.get()
        self.assertEqual(lr.days, D(3))
        # Too many days is refused
        r = self.client.post("/leave/", {"leave_type": al.pk, "start_date": "2026-11-02", "end_date": "2026-11-30"})
        self.assertContains(r, "Not enough Annual leave")
        self.login(self.hr_a)
        self.client.post("/leave/approvals/", {"id": lr.pk, "action": "approve"})
        lr.refresh_from_db()
        self.assertEqual(lr.status, LeaveRequest.APPROVED)

    def test_hr_request(self):
        self.login(self.emp_a)
        self.client.post("/requests/", {"category": "salary_confirmation", "subject": "Letter for bank loan"})
        r = HRRequest.objects.get()
        self.login(self.hr_a)
        self.client.post("/requests/manage/", {"id": r.pk, "status": "done", "response": "Emailed"})
        r.refresh_from_db()
        self.assertEqual(r.status, "done")

    def test_full_payroll_cycle(self):
        self.login(self.hr_a)
        r = self.client.post(f"/payroll/company/{self.a.pk}/", {"year": 2026, "month": 10})
        p = PayrollPeriod.objects.get()
        self.assertRedirects(r, f"/payroll/{p.pk}/")
        inp = p.inputs.get()
        data = {"form-TOTAL_FORMS": 1, "form-INITIAL_FORMS": 1, "form-0-id": inp.pk, "form-0-no_pay_days": 0,
                "form-0-ot_hours": 0, "form-0-bonus": 0, "form-0-epf_earnings": 0, "form-0-other_earnings": 0, "form-0-salary_advance": 5000,
                "form-0-welfare": 500, "form-0-loan_recovery": 0, "form-0-other_deductions": 0, "form-0-remarks": ""}
        self.client.post(f"/payroll/{p.pk}/", data)
        self.client.post(f"/payroll/{p.pk}/submit/")
        # Client HR cannot process
        self.client.post(f"/payroll/{p.pk}/process/")
        p.refresh_from_db()
        self.assertEqual(p.status, "submitted")
        self.login(self.admin)
        self.client.post(f"/payroll/{p.pk}/process/")
        slip = p.payslips.get()
        self.assertEqual(slip.epf_employee, D("2400.00"))   # 8% of basic only
        self.assertEqual(slip.gross_salary, D("50000.00"))
        self.assertEqual(slip.net_salary, D("42100.00"))    # 50000-2400-5000-500
        # Employee can't see it before approval
        self.login(self.emp_a)
        self.assertEqual(self.client.get(f"/payslip/{slip.pk}/").status_code, 403)
        self.login(self.hr_a)
        self.client.post(f"/payroll/{p.pk}/approve/")
        self.login(self.emp_a)
        self.assertContains(self.client.get(f"/payslip/{slip.pk}/"), "42,100.00")
        self.assertContains(self.client.get("/"), "October 2026")


import io  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import override_settings  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from .branding import contrast, palette_from_logo, theme  # noqa: E402

TMP_MEDIA = tempfile.mkdtemp()


def fake_logo():
    img = Image.new("RGBA", (300, 120), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 140, 110], fill=(20, 110, 90, 255))     # green
    d.rectangle([160, 10, 290, 110], fill=(240, 160, 30, 255))   # orange
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class BrandingTests(PortalFlowTests.__bases__[0]):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.a = test_company(name="Alpha Ltd", code="AL")
        self.hr = User.objects.create_user("al.hr", password="pw", role=User.CLIENT_HR, company=self.a,
                                           must_change_password=False)

    def test_palette_ignores_background(self):
        cols = palette_from_logo(io.BytesIO(fake_logo()))
        self.assertGreaterEqual(len(cols), 2)
        self.assertNotIn("#ffffff", cols)

    def test_light_colours_stay_readable(self):
        t = theme("#ffe066")
        self.assertGreaterEqual(contrast(t["brand"], "#ffffff"), 4.5)

    def test_upload_logo_sets_theme(self):
        self.client.force_login(self.hr)
        r = self.client.post("/branding/", {
            "logo": SimpleUploadedFile("logo.png", fake_logo(), content_type="image/png"),
            "brand_color": "#7d5f80", "accent_color": "#c9b3c9",
        })
        self.assertEqual(r.status_code, 302)
        self.a.refresh_from_db()
        self.assertTrue(self.a.use_own_theme)
        self.assertNotEqual(self.a.brand_color, "#7d5f80")   # picked from logo
        page = self.client.get("/")
        self.assertContains(page, self.a.theme()["brand"])
        self.assertContains(page, self.a.logo.url)

    def test_employee_cannot_change_branding(self):
        emp = Employee.objects.create(company=self.a, emp_no="1", full_name="X")
        u = User.objects.create_user("e1", password="pw", role=User.EMPLOYEE, company=self.a, employee=emp,
                                     must_change_password=False)
        self.client.force_login(u)
        self.assertEqual(self.client.get("/branding/").status_code, 403)


class SiteThemeTests(TestCase):
    def test_admin_changes_default_look(self):
        admin = User.objects.create_user("jay", password="pw", role=User.ADMIN, must_change_password=False)
        self.client.force_login(admin)
        r = self.client.post("/branding/?company=site", {"brand_color": "#2f6f73", "accent_color": "#a9cfd0",
                                                         "style": "tinted"})
        self.assertEqual(r.status_code, 302)
        page = self.client.get("/")
        self.assertContains(page, 'class="style-tinted"')
        self.assertContains(page, "--brand:#2f6f73")

    def test_client_cannot_edit_site_theme(self):
        c = test_company(name="A", code="A")
        hr = User.objects.create_user("h", password="pw", role=User.CLIENT_HR, company=c, must_change_password=False)
        self.client.force_login(hr)
        self.client.post("/branding/?company=site", {"brand_color": "#000000", "style": "minimal"})
        from .models import SiteTheme
        self.assertNotEqual(SiteTheme.current().style, "minimal")

    def test_company_style_saved(self):
        c = test_company(name="A", code="A")
        hr = User.objects.create_user("h", password="pw", role=User.CLIENT_HR, company=c, must_change_password=False)
        self.client.force_login(hr)
        self.client.post("/branding/", {"brand_color": "#2f6f73", "accent_color": "#a9cfd0",
                                        "use_own_theme": "on", "style": "tinted"})
        c.refresh_from_db()
        self.assertEqual(c.style, "tinted")
        self.assertContains(self.client.get("/"), 'class="style-tinted"')


from .models import SiteTheme

class DefaultLookTests(TestCase):
    def test_default_is_sage_bold(self):
        page = self.client.get("/login/")
        self.assertRedirects(page, "/app/login", fetch_redirect_response=False)
        self.assertEqual(SiteTheme.current().theme()["brand"], "#4f7462")

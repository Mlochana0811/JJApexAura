import hashlib
import io
import json
import tempfile
from datetime import date, datetime, timedelta, time
from decimal import Decimal as D
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from core.models import Employee, User, SalaryHistory
from leave.models import LeaveType, LeaveRequest, LeaveEntitlement, HRRequest, leave_balances
from payroll.models import PayrollPeriod, PayrollInput, Payslip, start_period, run_payroll
from payroll.engine import PayInputs, calculate
from payroll import statutory, exports
from .models import *
from .services import clock, payroll_action, submit_leave, decide_leave, correct_attendance
from .testing import company

@override_settings(CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache'}},EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class WorkflowTests(TestCase):
    def setUp(self):
        self.c=company(name='Alpha',code='A',epf_zone='A',epf_employer_no='123456')
        self.other=company(name='Beta',code='B')
        self.admin=User.objects.create_user('admin',password='SensiblePass!24',role='admin',must_change_password=False)
        self.hr=User.objects.create_user('hr',password='SensiblePass!24',role='client_hr',company=self.c,must_change_password=False)
        self.manager=User.objects.create_user('manager',role='manager',company=self.c,must_change_password=False)
        self.e=Employee.objects.create(company=self.c,emp_no='E1',full_name='Employee One',basic_salary=30000,bank_account='123456',nic='123456789V',epf_no='1',manager=self.manager,join_date=date(2025,1,1),email='e@example.invalid')
        self.e2=Employee.objects.create(company=self.c,emp_no='E2',full_name='Employee Two',basic_salary=40000)
        self.foreign=Employee.objects.create(company=self.other,emp_no='X',full_name='Outside',basic_salary=40000)
        self.employee=User.objects.create_user('employee',password='SensiblePass!24',role='employee',company=self.c,employee=self.e,must_change_password=False)
        LeaveType.seed_defaults(self.c)
        self.lt=LeaveType.objects.get(company=self.c,code='AL')
        self.client.force_login(self.admin)
    def post(self,url,data=None):return self.client.post(url,data=json.dumps(data or {}),content_type='application/json')
    def period(self):return start_period(self.c,2026,10)[0]
    def test_api_auth_required(self):
        self.client.logout();self.assertEqual(self.client.get('/api/employees/').status_code,401)
    def test_csrf_enforced(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post('/api/companies/',{},content_type='application/json').status_code,403)
    def test_forced_password_change(self):
        self.employee.must_change_password=True;self.employee.save();self.client.force_login(self.employee)
        self.assertEqual(self.client.get('/api/dashboard/').status_code,428)
        r=self.post('/api/auth/password/',{'old_password':'SensiblePass!24','password':'NewAndSecure!482'})
        self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(self.client.get('/api/dashboard/').status_code,200)
    def test_login_logout_and_reset_request(self):
        self.client.logout()
        r=self.post('/api/auth/login/',{'username':'employee','password':'SensiblePass!24'});self.assertEqual(r.status_code,200)
        self.assertEqual(self.post('/api/auth/logout/').status_code,200)
        self.assertEqual(self.post('/api/auth/reset-request/',{'email':'missing@example.invalid'}).status_code,200)
    def test_company_isolation(self):
        self.client.force_login(self.hr)
        self.assertEqual(self.client.get(f'/api/employees/{self.foreign.pk}/').status_code,404)
        self.assertEqual(len(self.client.get('/api/employees/').json()['items']),2)
    def test_manager_team_scope_and_salary_redaction(self):
        self.client.force_login(self.manager)
        items=self.client.get('/api/employees/').json()['items']
        self.assertEqual(len(items),1);self.assertNotIn('basic_salary',items[0]);self.assertNotIn('bank_account',items[0])
        self.assertEqual(self.client.get('/api/payroll/').status_code,403)
        self.assertEqual(self.client.get(f'/api/schema/employees/{self.e.pk}/').status_code,403)
    def test_employee_cannot_create_or_promote(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.post('/api/employees/',{}).status_code,403)
        self.assertEqual(self.post(f'/api/employees/{self.e.pk}/account/',{'role':'client_hr'}).status_code,403)
    def test_all_admin_lists(self):
        from .api import RESOURCES
        p=self.period()
        for name in RESOURCES:
            path=f'/api/{name}/'+(f'?period={p.pk}' if name=='inputs' else '')
            with self.subTest(resource=name):self.assertEqual(self.client.get(path).status_code,200)
    def test_create_company_and_seed_leave_types(self):
        data={'name':'New','code':'NEW','working_weekdays':[0,1,2,3,4],'payday':10,'no_pay_divisor':30,'ot_hourly_divisor':240,'ot_multiplier':'1.5','payroll_cutoff_day':25,'is_active':True}
        r=self.post('/api/companies/',data);self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(LeaveType.objects.filter(company_id=r.json()['item']['id']).count(),5)
    def test_employee_creation_and_salary_change(self):
        data={'company':self.c.pk,'emp_no':'E3','full_name':'New colleague','status':'active','basic_salary':'35000','epf_allowance':'0','fixed_allowance':'0','epf_eligible':True,'apit_applicable':True}
        r=self.post('/api/employees/',data);self.assertEqual(r.status_code,201,r.content)
        pk=r.json()['item']['id'];self.assertEqual(SalaryHistory.objects.filter(employee_id=pk).count(),1)
        self.assertEqual(ChecklistItem.objects.filter(employee_id=pk).count(),4)
        r=self.post('/api/salaries/',{'employee':pk,'effective_date':'2027-01-01','basic_salary':'45000','epf_allowance':'0','fixed_allowance':'0','reason':'Review'})
        self.assertEqual(r.status_code,201,r.content)
    def test_invalid_pay_inputs_rejected(self):
        for opts in ({'ot_hours':-1},{'no_pay_days':40},{'no_pay_divisor':0},{'ot_hourly_divisor':0}):
            with self.subTest(opts=opts),self.assertRaises(ValueError):calculate(PayInputs(basic_salary=30000,**opts))
        p=self.period();inp=p.inputs.get(employee=self.e)
        r=self.post(f'/api/inputs/{inp.pk}/',{'ot_hours':-1,'no_pay_days':0,'bonus':0,'epf_earnings':0,'other_earnings':0,'salary_advance':0,'welfare':0,'loan_recovery':0,'other_deductions':0})
        self.assertEqual(r.status_code,400)
    def test_no_one_off_carry_forward(self):
        p=self.period();i=p.inputs.get(employee=self.e);i.bonus=1000;i.salary_advance=2000;i.welfare=100;i.save()
        nextp=start_period(self.c,2026,11)[0];i=nextp.inputs.get(employee=self.e)
        self.assertEqual((i.bonus,i.salary_advance,i.welfare),(0,0,100))
    def test_processing_atomic_rollback(self):
        p=self.period();i=p.inputs.get(employee=self.e2);i.other_deductions=999999;i.save()
        with self.assertRaises(ValidationError):payroll_action(self.admin,p.pk,'process')
        self.assertFalse(p.payslips.exists());p.refresh_from_db();self.assertEqual(p.status,'open')
    def test_policy_review_required(self):
        self.c.payrollpolicy_set.update(reviewed=False)
        with self.assertRaises(ValidationError):run_payroll(self.period())
    def test_bonus_requires_tax_review(self):
        p=self.period();i=p.inputs.get(employee=self.e);i.bonus=1000;i.save()
        with self.assertRaises(ValidationError):run_payroll(p)
        i.apit_override=0;i.tax_note='Reviewed test fixture';i.save();run_payroll(p)
    def test_approval_lock_and_stale_input_protection(self):
        p=self.period();payroll_action(self.admin,p.pk,'process')
        inp=p.inputs.get(employee=self.e);inp.welfare=900
        with self.assertRaises(ValidationError):inp.save()
        payroll_action(self.hr,p.pk,'approve');payroll_action(self.admin,p.pk,'lock')
        with self.assertRaises(ValidationError):payroll_action(self.admin,p.pk,'reopen')
        payroll_action(self.hr,p.pk,'paid',{'reference':'BANK-001'});p.refresh_from_db();self.assertEqual(p.payment_status,'paid')
        with self.assertRaises(ValidationError):payroll_action(self.hr,p.pk,'paid',{'reference':'again'})
    def test_reopen_invalidates_and_archives_results(self):
        p=self.period();payroll_action(self.admin,p.pk,'process');payroll_action(self.hr,p.pk,'approve');payroll_action(self.admin,p.pk,'reopen')
        self.assertFalse(p.payslips.exists());self.assertTrue(AuditEvent.objects.filter(action='payroll.superseded').exists())
        p.refresh_from_db();self.assertIsNone(p.approved_at)
    def test_historical_employee_and_company_frozen(self):
        p=self.period();payroll_action(self.admin,p.pk,'process');p.refresh_from_db()
        self.e.bank_account='CHANGED';self.e.epf_eligible=False;self.e.save();self.c.epf_employer_no='999999';self.c.save()
        s=p.payslips.get(employee=self.e);self.assertEqual(s.frozen_employee.bank_account,'123456')
        self.assertEqual(p.frozen_company.epf_employer_no,'123456');self.assertIn('1',[m.member_no for m in statutory.members(p)])
    def test_effective_salary_and_joiner_proration(self):
        self.e.join_date=date(2026,10,16);self.e.basic_salary=31000;self.e.save()
        SalaryHistory.objects.create(employee=self.e,effective_date=date(2026,10,16),basic_salary=31000,fixed_allowance=0)
        p=self.period();run_payroll(p);self.assertEqual(p.payslips.get(employee=self.e).basic_salary,D('16000'))
    def test_resigned_employee_paid_for_worked_month(self):
        self.e.status='resigned';self.e.leave_date=date(2026,10,15);self.e.save()
        p=self.period();run_payroll(p);self.assertTrue(p.payslips.filter(employee=self.e).exists())
    def test_loan_repayment_once_at_lock(self):
        loan=Loan.objects.create(employee=self.e,principal=3000,installment=1000,start_date=date(2026,1,1),status='approved')
        p=self.period();payroll_action(self.admin,p.pk,'process');self.assertEqual(loan.balance,3000)
        payroll_action(self.hr,p.pk,'approve');payroll_action(self.admin,p.pk,'lock')
        self.assertEqual(loan.balance,2000)
        with self.assertRaises(ValidationError):payroll_action(self.admin,p.pk,'lock')
        self.assertEqual(LoanRepayment.objects.filter(loan=loan).count(),1)
    def test_clock_sequence_and_double_checkin(self):
        a=clock(self.employee,'in')
        with self.assertRaises(ValidationError):clock(self.employee,'in')
        clock(self.employee,'break-start')
        with self.assertRaises(ValidationError):clock(self.employee,'break-start')
        clock(self.employee,'break-end');clock(self.employee,'out');a.refresh_from_db()
        self.assertIsNotNone(a.check_out);self.assertEqual(a.breaks.count(),1)
    def test_attendance_correction_approval(self):
        now=timezone.now();c=AttendanceCorrection.objects.create(employee=self.e,requested_in=now-timedelta(hours=9),requested_out=now-timedelta(hours=1),reason='Missed check-in')
        correct_attendance(self.manager,c,True);c.refresh_from_db();self.assertEqual(c.status,'approved');self.assertEqual(c.attendance.worked_hours,8)
    def test_overnight_attendance(self):
        start=timezone.make_aware(datetime(2026,10,10,22))
        with patch('workforce.services.timezone.now',return_value=start):a=clock(self.employee,'in')
        with patch('workforce.services.timezone.now',return_value=start+timedelta(hours=8)):clock(self.employee,'out')
        a.refresh_from_db();self.assertEqual(a.worked_hours,8)
    def test_cross_year_leave_uses_separate_entitlements(self):
        lr=LeaveRequest(employee=self.e,leave_type=self.lt,start_date=date(2026,12,31),end_date=date(2027,1,4))
        submit_leave(self.employee,lr);decide_leave(self.hr,lr.pk,'approve')
        b26=next(b for b in leave_balances(self.e,2026) if b['type']==self.lt);b27=next(b for b in leave_balances(self.e,2027) if b['type']==self.lt)
        self.assertEqual((b26['used'],b27['used']),(1,2))
    def test_holiday_and_weekend_half_day(self):
        Holiday.objects.create(company=self.c,date=date(2026,10,12),name='Company holiday')
        for day in [date(2026,10,12),date(2026,10,11)]:
            with self.assertRaises(ValidationError):submit_leave(self.employee,LeaveRequest(employee=self.e,leave_type=self.lt,start_date=day,end_date=day,half_day=True))
    def test_future_leave_uses_future_balance(self):
        LeaveEntitlement.objects.create(employee=self.e,leave_type=self.lt,year=2027,days=0)
        with self.assertRaises(ValidationError):submit_leave(self.employee,LeaveRequest(employee=self.e,leave_type=self.lt,start_date=date(2027,1,4),end_date=date(2027,1,4)))
    def test_calendar_change_does_not_rewrite_approved_leave(self):
        lr=LeaveRequest(employee=self.e,leave_type=self.lt,start_date=date(2026,10,12),end_date=date(2026,10,12));submit_leave(self.employee,lr);decide_leave(self.hr,lr.pk,'approve')
        Holiday.objects.create(company=self.c,date=date(2026,10,12),name='Added later')
        b=next(b for b in leave_balances(self.e,2026) if b['type']==self.lt);self.assertEqual(b['used'],1)
    def test_manager_cannot_approve_own_leave(self):
        self.employee.employee=None;self.employee.save()
        self.manager.employee=self.e;self.manager.save()
        lr=LeaveRequest(employee=self.e,leave_type=self.lt,start_date=date(2026,10,12),end_date=date(2026,10,12));submit_leave(self.manager,lr)
        with self.assertRaises(PermissionDenied):decide_leave(self.manager,lr.pk,'approve')
    def test_no_pay_sync(self):
        lt=LeaveType.objects.get(company=self.c,code='NP');lr=LeaveRequest(employee=self.e,leave_type=lt,start_date=date(2026,10,12),end_date=date(2026,10,13));submit_leave(self.employee,lr);decide_leave(self.hr,lr.pk,'approve')
        p=self.period();payroll_action(self.hr,p.pk,'sync_leave');self.assertEqual(p.inputs.get(employee=self.e).no_pay_days,2)
    def test_request_thread_and_announcements(self):
        req=HRRequest.objects.create(employee=self.e,subject='Please help',category='other')
        self.client.force_login(self.employee);r=self.post(f'/api/requests/{req.pk}/reply/',{'message':'More details'});self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(req.messages.count(),1)
        ann=Announcement.objects.create(company=self.c,title='News',body='Welcome')
        self.assertEqual(self.post(f'/api/announcements/{ann.pk}/acknowledge/').status_code,200)
        self.assertEqual(self.post(f'/api/announcements/{ann.pk}/acknowledge/').status_code,200);self.assertEqual(Acknowledgement.objects.count(),1)
    def test_private_document_download(self):
        with tempfile.TemporaryDirectory() as tmp,override_settings(MEDIA_ROOT=tmp):
            self.client.force_login(self.employee)
            r=self.client.post('/api/documents/',{'title':'Contract','kind':'contract','file':SimpleUploadedFile('contract.pdf',b'%PDF-1.4 demo',content_type='application/pdf')})
            self.assertEqual(r.status_code,201,r.content);pk=r.json()['item']['id']
            self.assertEqual(self.client.get(f'/api/files/{pk}/').status_code,200)
            otherhr=User.objects.create_user('otherhr',role='client_hr',company=self.other,must_change_password=False);self.client.force_login(otherhr)
            self.assertEqual(self.client.get(f'/api/files/{pk}/').status_code,404)
    def test_invite_single_use(self):
        r=self.post(f'/api/employees/{self.e2.pk}/invite/');self.assertEqual(r.status_code,400) # missing email
        self.e2.email='new@example.invalid';self.e2.save()
        r=self.post(f'/api/employees/{self.e2.pk}/invite/');self.assertEqual(r.status_code,200,r.content)
        from django.core import mail
        token=mail.outbox[-1].body.rsplit('/',1)[-1]
        self.client.logout();payload={'token':token,'username':'new','password':'UniqueStrong!473'}
        self.assertEqual(self.post('/api/auth/accept-invite/',payload).status_code,200)
        self.assertEqual(self.post('/api/auth/accept-invite/',payload).status_code,400)
    def test_salary_and_payslip_pdf_reports(self):
        p=self.period();payroll_action(self.admin,p.pk,'process');payroll_action(self.hr,p.pk,'approve')
        for path in [f'/api/reports/salary-letter/{self.e.pk}/',f'/api/reports/payslip/{p.payslips.get(employee=self.e).pk}/',f'/api/reports/variance/{p.pk}/']:
            r=self.client.get(path);self.assertEqual(r.status_code,200,r.content[:200]);self.assertTrue(r.content.startswith(b'%PDF'))
    def test_payslip_formats_batch_and_access(self):
        p=self.period();payroll_action(self.admin,p.pk,'process')
        url=f'/api/reports/payslip-batch/{p.pk}/'
        self.assertEqual(self.client.get(url).status_code,400)
        payroll_action(self.hr,p.pk,'approve')
        for template in ('navy','classic'):
            r=self.client.get(url,{'template':template})
            self.assertEqual(r.status_code,200);self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertEqual(self.client.get(url,{'template':'invalid'}).status_code,400)
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(url).status_code,403)
        own=p.payslips.get(employee=self.e)
        self.assertEqual(self.client.get(f'/api/reports/payslip/{own.pk}/?template=classic').status_code,200)
        other=p.payslips.get(employee=self.e2)
        self.assertEqual(self.client.get(f'/api/reports/payslip/{other.pk}/').status_code,404)
    def test_unapproved_payslip_hidden(self):
        p=self.period();payroll_action(self.admin,p.pk,'process');self.client.force_login(self.employee)
        self.assertEqual(self.client.get('/api/payslips/').json()['count'],0)
    def test_offboarding_disables_account(self):
        from .api import form_for
        from django.forms.models import model_to_dict
        data=model_to_dict(self.e);data.update(status='resigned',leave_date='2026-10-14',join_date='2025-01-01',date_of_birth=None)
        for k in ['basic_salary','epf_allowance','fixed_allowance']:data.pop(k,None)
        r=self.post(f'/api/employees/{self.e.pk}/',data);self.assertEqual(r.status_code,200,r.content)
        self.employee.refresh_from_db();self.assertFalse(self.employee.is_active)
    def test_locked_model_and_admin_read_only(self):
        from django.contrib import admin
        p=self.period();payroll_action(self.admin,p.pk,'process');payroll_action(self.hr,p.pk,'approve');payroll_action(self.admin,p.pk,'lock')
        p.refresh_from_db();p.status='open'
        with self.assertRaises(ValidationError):p.save()
        self.assertFalse(admin.site._registry[PayrollPeriod].has_change_permission(None))

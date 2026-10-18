"""Opt-in synthetic data; never runs automatically during production deployment."""
from datetime import date, time, timedelta, datetime
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from core.models import Company, Employee, User, SalaryHistory
from leave.models import LeaveType, HRRequest
from payroll.models import start_period
from workforce.models import Shift, Roster, Attendance, Announcement, ChecklistItem, PayrollPolicy, Asset
from workforce.services import payroll_action
from workforce.testing import BANDS
class Command(BaseCommand):
    help='Create a local demonstration workspace using fictional employees'
    def add_arguments(self, parser):parser.add_argument('--password',required=True,help='Temporary password for demo accounts')
    @transaction.atomic
    def handle(self,*args,**options):
        if not settings.DEBUG:raise CommandError('Demo seeding is disabled with DEBUG=False')
        if User.objects.filter(username='demo.admin').exists():raise CommandError('Demo accounts already exist; no changes made')
        password=options['password']
        from django.contrib.auth.password_validation import validate_password
        validate_password(password)
        business=[]
        for name,code in [('JJApexAura Call Center','CALL'),('JJApexAura IT Solutions','IT'),('JJApexAura Gem & Jewellery','GEM'),('JJApexAura Property','PROP')]:
            c,_=Company.objects.get_or_create(code=code,defaults={'name':name,'epf_zone':'A','epf_employer_no':'999999','payday':10})
            LeaveType.seed_defaults(c);business.append(c)
            PayrollPolicy.objects.get_or_create(company=c,name='DEMO ONLY — review before real payroll',defaults={'effective_date':date(2025,4,1),'reviewed':True,'source_note':'Synthetic demo fixture; not certified for live payroll. Replace with a reviewed policy for real employees.','bands':BANDS})
        c=business[0]
        def account(username,role,employee=None):
            return User.objects.create_user(username,password=password,role=role,company=None if role=='admin' else c,employee=employee,first_name={'admin':'Jay','client_hr':'HR','manager':'Team lead','employee':'Alex'}[role],email=f'{username}@example.invalid',must_change_password=True,is_staff=role=='admin',is_superuser=role=='admin')
        admin=account('demo.admin','admin');hr=account('demo.hr','client_hr');manager=account('demo.manager','manager')
        today=timezone.localdate();shift=Shift.objects.create(company=c,name='Day shift',start_time=time(9),end_time=time(18),expected_hours=8)
        for i,name in enumerate(['Alex Fernando','Maya Silva','Sam Perera','Taylor Raj','Robin James','Jamie Deen','Casey Kumar','Jordan Lee'],1):
            e=Employee.objects.create(company=c,emp_no=f'DEMO{i:03}',full_name=name,designation='Customer success agent',department='Customer operations',join_date=date(2025,1,1),basic_salary=Decimal(40000+i*2500),epf_allowance=5000,fixed_allowance=10000,manager=manager,nic=f'DEMO-NIC-{i}',epf_no=str(i),bank_name='Demo Bank',bank_account=f'000000{i:04}',email=f'employee{i}@example.invalid')
            SalaryHistory.objects.create(employee=e,effective_date=e.join_date,basic_salary=e.basic_salary,epf_allowance=e.epf_allowance,fixed_allowance=e.fixed_allowance,reason='Demo opening salary')
            roster=Roster.objects.create(employee=e,shift=shift,date=today)
            if i<=4:
                start=timezone.make_aware(datetime.combine(today,time(9)))
                Attendance.objects.create(employee=e,date=today,check_in=start,check_out=start+timedelta(hours=8),roster=roster)
            ChecklistItem.objects.create(employee=e,title='Complete induction',completed=i<5)
            if i==1:
                account('demo.employee','employee',e)
                HRRequest.objects.create(employee=e,category='salary_confirmation',subject='Employment letter request',details='Please prepare a letter for my records.')
                Asset.objects.create(company=c,employee=e,name='Work laptop',serial_number='DEMO-LAPTOP-001',issued_on=today,condition='Good')
        Announcement.objects.create(company=c,title='Welcome to your new HR workspace',body='Manage your time, request leave and stay connected with HR from one place.',created_by=hr)
        Announcement.objects.create(company=c,title='Keep your employee details up to date',body='Please review your contact and bank details. Send a request to HR if anything needs to change.',created_by=hr)
        # Show real calculated history from synthetic employees.
        for offset in [3,2,1]:
            idx=today.year*12+today.month-1-offset;y,m=divmod(idx,12)
            p,_=start_period(c,y,m+1)
            if p.status=='open':
                payroll_action(admin,p.pk,'process');payroll_action(hr,p.pk,'approve');payroll_action(admin,p.pk,'lock')
        start_period(c,today.year,today.month)
        self.stdout.write(self.style.SUCCESS('Demo ready: demo.admin, demo.hr, demo.manager, demo.employee. Use your chosen password; each account must change it at first sign-in. All data is fictional.'))

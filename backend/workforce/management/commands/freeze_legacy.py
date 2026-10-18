"""Explicitly freeze available master data for pre-v2 payroll; cannot reconstruct old bank details."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from payroll.models import PayrollPeriod, Payslip
from workforce.models import AuditEvent
class Command(BaseCommand):
    help='Freeze legacy snapshot gaps using current master data, explicitly labelled as backfilled'
    def add_arguments(self,parser):parser.add_argument('--accept-current-details',action='store_true')
    @transaction.atomic
    def handle(self,*args,**options):
        missing=Payslip.objects.filter(snapshot={}).count()
        self.stdout.write(f'{missing} legacy payslip snapshots missing')
        if not options['accept_current_details']:
            self.stdout.write('Dry run. Historical personal/bank details cannot be recovered from v1.5. Review a backup, then pass --accept-current-details to preserve the currently available details.');return
        for s in Payslip.objects.select_for_update().filter(snapshot={}):
            e=s.employee
            snapshot={f:str(getattr(e,f) or '') for f in ('emp_no','full_name','designation','nic','email','bank_name','bank_branch','bank_account','epf_no','epf_occupation_grade','join_date','leave_date')}
            snapshot.update(surname=e.epf_name()[0],initials=e.epf_name()[1],epf_eligible=bool(s.epf_base),days='0',loan_deductions=[],backfilled_from_current_details=True)
            inp=s.period.inputs.filter(employee=e).first()
            if inp:snapshot['days']=str(max(0,s.period.company.no_pay_divisor-inp.no_pay_days))
            Payslip.objects.filter(pk=s.pk).update(snapshot=snapshot)
            AuditEvent.objects.create(company=s.period.company,action='migration.freeze-current-details',entity='payroll.Payslip',object_id=str(s.pk),after={'backfilled_from_current_details':True})
        for p in PayrollPeriod.objects.select_for_update().filter(company_snapshot={}):
            c=p.company
            snapshot={f:getattr(c,f) for f in ('name','code','address','epf_zone','epf_employer_no','epf_district_office','etf_reg_no','tin','epf_reg_no','no_pay_divisor')}
            PayrollPeriod.objects.filter(pk=p.pk).update(company_snapshot=snapshot)
        self.stdout.write('Available details frozen. Backfilled snapshots are explicitly marked; validate them against original records.')

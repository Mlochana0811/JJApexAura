import csv
from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import Company, Employee, SalaryHistory
class Command(BaseCommand):
    help='Import new employees from UTF-8 CSV; never overwrite existing employee records'
    def add_arguments(self,parser):
        parser.add_argument('file');parser.add_argument('--company',required=True);parser.add_argument('--commit',action='store_true')
    @transaction.atomic
    def handle(self,*args,**options):
        try:c=Company.objects.get(code=options['company'])
        except Company.DoesNotExist:raise CommandError('Create the company first')
        count=0
        with open(options['file'],newline='',encoding='utf-8-sig') as stream:
            for row in csv.DictReader(stream):
                if not row.get('emp_no') or not row.get('full_name'):raise CommandError('emp_no and full_name are required')
                if Employee.objects.filter(company=c,emp_no=row['emp_no']).exists():raise CommandError(f'Employee {row["emp_no"]} already exists; nothing imported')
                salary=Decimal(row.get('basic_salary') or 0)
                if salary<0:raise CommandError('Salary must not be negative')
                emp=Employee(company=c,emp_no=row['emp_no'],full_name=row['full_name'],email=row.get('email',''),department=row.get('department',''),designation=row.get('designation',''),phone=row.get('phone',''),nic=row.get('nic',''),bank_name=row.get('bank_name',''),bank_account=row.get('bank_account',''),epf_no=row.get('epf_no',''),basic_salary=salary,join_date=date.fromisoformat(row['join_date']) if row.get('join_date') else None)
                emp.full_clean();emp.save()
                SalaryHistory.objects.create(employee=emp,effective_date=emp.join_date or date.today(),basic_salary=salary,fixed_allowance=0,reason='CSV import')
                count+=1
        if not options['commit']:transaction.set_rollback(True)
        self.stdout.write(f'{count} employees '+('imported' if options['commit'] else 'validated; rerun with --commit to save'))

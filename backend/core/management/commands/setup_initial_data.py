"""Load the client companies and employees found in Google Drive, and create logins.

    python manage.py setup_initial_data            # random passwords, saved to data/initial_logins.csv
    python manage.py setup_initial_data --basic 30000
"""
import csv
import json
import secrets
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Company, Employee, SalaryHistory, User
from leave.models import LeaveType


def new_password():
    return "JHR-" + secrets.token_urlsafe(6)


class Command(BaseCommand):
    help = "Import Clever Growth and Synergy Core employees and create portal logins"

    def add_arguments(self, parser):
        parser.add_argument("--update-existing", action="store_true", help="Explicitly allow replacing existing employee master fields")
        parser.add_argument("--source", required=True, help="Explicit path to the original initial_employees.json")
        parser.add_argument("--basic", type=int, default=30000,
                            help="Basic salary (EPF/ETF base); the rest of pay becomes fixed allowance")
        parser.add_argument("--password", help="Use one password for every login (testing only)")

    @transaction.atomic
    def handle(self, *args, basic, password, **opts):
        source = Path(opts["source"])
        if not source.is_file(): raise CommandError("Source JSON not found")
        data = json.loads(source.read_text())
        logins = []

        def make_user(username, role, first_name, company=None, employee=None, superuser=False):
            if User.objects.filter(username=username).exists():
                return
            pw = password or new_password()
            u = User(username=username, role=role, first_name=first_name, company=company,
                     employee=employee, is_staff=superuser, is_superuser=superuser)
            u.set_password(pw)
            u.save()
            logins.append([username, pw, role, company.name if company else "All", first_name])

        make_user("jay", User.ADMIN, "Jay", superuser=True)

        for c in data["companies"]:
            company, _ = Company.objects.get_or_create(code=c["code"], defaults={"name": c["name"]})
            LeaveType.seed_defaults(company)
            make_user(f"{c['code'].lower()}.hr", User.CLIENT_HR, f"{c['name']} HR", company=company)
            for e in c["employees"]:
                total = Decimal(e.pop("total"))
                b = min(Decimal(basic), total)
                fields = {k: v for k, v in e.items() if k in {f.name for f in Employee._meta.fields}}
                fields.update(basic_salary=b, fixed_allowance=total - b, epf_eligible=e.get("epf", True))
                if Employee.objects.filter(company=company, emp_no=e["emp_no"]).exists() and not opts["update_existing"]:
                    raise CommandError("Matching employees already exist. Use a separate test database or explicitly pass --update-existing after backup.")
                emp, created = Employee.objects.update_or_create(
                    company=company, emp_no=e["emp_no"], defaults=fields)
                if created:
                    SalaryHistory.objects.create(employee=emp, effective_date=date.today(), basic_salary=b,
                                                 fixed_allowance=total - b, reason="Imported from Drive")
                if emp.status != Employee.RESIGNED:
                    make_user(emp.emp_no.lower(), User.EMPLOYEE, emp.full_name, company=company, employee=emp)

        out = Path(settings.BASE_DIR) / "data" / "initial_logins.csv"
        if logins:
            with out.open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["user_id", "temporary_password", "role", "company", "name"])
                w.writerows(logins)
        self.stdout.write(self.style.SUCCESS(
            f"{Company.objects.count()} companies, {Employee.objects.count()} employees, "
            f"{len(logins)} new logins → {out.name}"))

import calendar
import hashlib
import json
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.db import models
from django.forms.models import model_to_dict
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from core.models import Employee, User
from core.access import visible_employees
from leave.models import LeaveRequest, leave_balances
from payroll.models import PayrollPeriod, PayrollInput, run_payroll, copy_inputs, eligible_employees
from .models import *

def plain(obj):
    data = model_to_dict(obj)
    for field in ("password", "token_hash"): data.pop(field, None)
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder, default=str))

def audit(user, action, obj, before=None):
    company_id = getattr(obj, "company_id", None)
    if not company_id and getattr(obj, "employee_id", None): company_id = obj.employee.company_id
    if not company_id and getattr(obj, "period_id", None): company_id = obj.period.company_id
    AuditEvent.objects.create(actor=user, company_id=company_id, action=action,
        entity=obj._meta.label, object_id=str(obj.pk), before=before or {}, after=plain(obj))

def notify(employee, text):
    for u in User.objects.filter(employee=employee, is_active=True):
        Notification.objects.create(user=u, text=text[:250])

def notify_hr(employee, text):
    for u in User.objects.filter(company=employee.company, role=User.CLIENT_HR, is_active=True):
        Notification.objects.create(user=u, text=text[:250])

def require_hr(user):
    if not (user.is_hr_admin or user.is_client_hr): raise PermissionDenied("HR access required")

def require_team(user, emp):
    if not visible_employees(user).filter(pk=emp.pk).exists(): raise PermissionDenied("Employee is outside your scope")

def workdays(company, start, end):
    weekdays = company.working_weekdays or [0,1,2,3,4]
    holidays = set(Holiday.objects.filter(company=company, date__range=(start,end)).values_list("date", flat=True))
    day = start
    while day <= end:
        if day.weekday() in weekdays and day not in holidays: yield day
        day += timedelta(days=1)

def leave_allocations(lr):
    end = lr.start_date if lr.half_day else lr.end_date
    result = {}
    for day in workdays(lr.employee.company, lr.start_date, end):
        result[day.year] = result.get(day.year, Decimal(0)) + (Decimal("0.5") if lr.half_day else Decimal(1))
    return result

def validate_leave(lr):
    if lr.end_date < lr.start_date: raise ValidationError("End date must follow start date")
    if lr.leave_type.company_id != lr.employee.company_id: raise ValidationError("Leave type belongs to another company")
    if LeaveRequest.objects.filter(employee=lr.employee, status__in=["pending","approved"],
        start_date__lte=lr.end_date, end_date__gte=lr.start_date).exclude(pk=lr.pk).exists():
        raise ValidationError("Leave overlaps an existing request")
    allocation = leave_allocations(lr)
    if not allocation: raise ValidationError("Selected dates are not working days")
    for year, days in allocation.items():
        balances = leave_balances(lr.employee, year, exclude_id=lr.pk)
        b = next(b for b in balances if b["type"].pk == lr.leave_type_id)
        if b["remaining"] is not None and days > b["remaining"] - b["pending"]:
            raise ValidationError(f"Not enough {lr.leave_type.name} available in {year}")

@transaction.atomic
def submit_leave(user, lr):
    Employee.objects.select_for_update().get(pk=lr.employee_id)
    validate_leave(lr)
    lr.save(); audit(user, "leave.create", lr)
    notify_hr(lr.employee, f"Leave requested by {lr.employee.full_name}")
    return lr

@transaction.atomic
def decide_leave(user, pk, action, comment=""):
    lr = LeaveRequest.objects.select_for_update().select_related("employee").get(pk=pk)
    require_team(user, lr.employee)
    if user.role not in ("admin","client_hr","manager") and not user.is_superuser: raise PermissionDenied
    if user.employee_id == lr.employee_id: raise PermissionDenied("Another approver must review your leave")
    Employee.objects.select_for_update().get(pk=lr.employee_id)
    if action not in ("approve","reject") or lr.status != "pending": raise ValidationError("Request is no longer pending")
    before = plain(lr)
    if action == "approve": validate_leave(lr)
    lr.status = "approved" if action == "approve" else "rejected"
    lr.decided_by=user; lr.decided_at=timezone.now(); lr.hr_comment=comment
    lr.save(); audit(user, "leave."+action, lr, before)
    notify(lr.employee, f"Leave request {lr.status}")
    return lr

@transaction.atomic
def clock(user, action):
    if not user.employee_id: raise ValidationError("Link your account to an employee first")
    emp = Employee.objects.select_for_update().get(pk=user.employee_id)
    if emp.status != Employee.ACTIVE: raise PermissionDenied("Employee is not active")
    now = timezone.now()
    session = Attendance.objects.select_for_update().filter(employee=emp, check_out__isnull=True).first()
    if action == "in":
        if session: raise ValidationError("You already have an open session")
        today=timezone.localdate()
        roster = Roster.objects.filter(employee=emp, date=today).select_related("shift").first()
        previous = Roster.objects.filter(employee=emp, date=today-timedelta(days=1)).select_related("shift").first()
        if previous and previous.shift.start_time > previous.shift.end_time and timezone.localtime(now).time() < previous.shift.end_time:
            roster = previous
        late=0
        if roster:
            start=timezone.make_aware(datetime.combine(roster.date,roster.shift.start_time))
            late=max(0,int((now-start).total_seconds()/60)-roster.shift.grace_minutes)
        session=Attendance.objects.create(employee=emp,date=today,check_in=now,roster=roster,late_minutes=late)
    elif not session: raise ValidationError("Check in first")
    elif action == "out":
        Break.objects.filter(attendance=session,end__isnull=True).update(end=now)
        session.check_out=now;session.save()
    elif action == "break-start":
        if session.breaks.filter(end__isnull=True).exists(): raise ValidationError("Break already started")
        Break.objects.create(attendance=session,start=now)
    elif action == "break-end":
        b=session.breaks.filter(end__isnull=True).first()
        if not b: raise ValidationError("No break is active")
        b.end=now;b.save()
    else: raise ValidationError("Unknown attendance action")
    audit(user,"attendance."+action,session)
    return session

@transaction.atomic
def correct_attendance(user, correction, approve):
    correction=AttendanceCorrection.objects.select_for_update().get(pk=correction.pk)
    require_team(user,correction.employee)
    if user.role not in ("admin","client_hr","manager") and not user.is_superuser: raise PermissionDenied
    if user.employee_id==correction.employee_id: raise PermissionDenied("Another approver must review your correction")
    if correction.status!="pending": raise ValidationError("Already decided")
    Employee.objects.select_for_update().get(pk=correction.employee_id)
    if approve:
        if correction.requested_out<=correction.requested_in: raise ValidationError("Check-out must follow check-in")
        qs=Attendance.objects.filter(employee=correction.employee,check_in__lt=correction.requested_out).filter(
            models.Q(check_out__isnull=True)|models.Q(check_out__gt=correction.requested_in)).exclude(pk=correction.attendance_id)
        if qs.exists(): raise ValidationError("Correction overlaps another attendance session")
        a=correction.attendance or Attendance(employee=correction.employee)
        if a.employee_id!=correction.employee_id: raise ValidationError("Employee mismatch")
        for b in a.breaks.all() if a.pk else []:
            if b.start<correction.requested_in or not b.end or b.end>correction.requested_out:
                raise ValidationError("Existing breaks fall outside corrected times; resolve the session first")
        before=plain(a) if a.pk else {}
        a.check_in=correction.requested_in;a.check_out=correction.requested_out;a.date=timezone.localtime(a.check_in).date();a.save()
        correction.attendance=a;audit(user,"attendance.correct",a,before)
    correction.status="approved" if approve else "rejected";correction.decided_by=user;correction.save()
    audit(user,"correction.decide",correction);notify(correction.employee,f"Attendance correction {correction.status}")

@transaction.atomic
def payroll_action(user, pk, action, data=None):
    from django.db import models
    data=data or {}
    require_hr(user)
    p=PayrollPeriod.objects.select_for_update().get(pk=pk)
    if not user.is_hr_admin and user.company_id!=p.company_id: raise PermissionDenied
    before=plain(p)
    if action=="submit" and p.status==p.OPEN:
        p.status=p.SUBMITTED;p.submitted_at=timezone.now()
    elif action=="process" and user.is_hr_admin and p.status in (p.OPEN,p.SUBMITTED,p.PROCESSED):
        audit(user,"payroll.previous-calculation",p,{"slips":json.loads(json.dumps(list(p.payslips.values()),cls=DjangoJSONEncoder))})
        run_payroll(p);p.refresh_from_db();p.status=p.PROCESSED;p.processed_at=timezone.now()
    elif action=="approve" and p.status==p.PROCESSED:
        if not p.payslips.exists(): raise ValidationError("Process payroll first")
        p.status=p.APPROVED;p.approved_at=timezone.now();p.approved_by=user
        for slip in p.payslips.all(): notify(slip.employee,f"Your payslip for {p.label} is available")
    elif action=="lock" and user.is_hr_admin and p.status==p.APPROVED:
        # Repayments are committed once, together with the final lock.
        for slip in p.payslips.all():
            for deduction in slip.snapshot.get("loan_deductions",[]):
                loan=Loan.objects.select_for_update().get(pk=deduction["id"])
                amount=Decimal(deduction["amount"])
                if amount>loan.balance: raise ValidationError("Loan balance changed; reopen and recalculate")
                LoanRepayment.objects.get_or_create(loan=loan,period=p,defaults={"amount":amount})
                if loan.balance<=0: loan.status="repaid";loan.save()
        p.status=p.LOCKED
    elif action=="reopen" and user.is_hr_admin and p.status in (p.SUBMITTED,p.PROCESSED,p.APPROVED):
        audit(user,"payroll.superseded",p,{"slips":json.loads(json.dumps(list(p.payslips.values()),cls=DjangoJSONEncoder))})
        p.status=p.OPEN;p.approved_at=None;p.approved_by=None;p.processed_at=None;p.save()
        p.payslips.all().delete()
    elif action=="copy_previous" and p.status==p.OPEN:
        prev=p.previous()
        if not prev: raise ValidationError("No previous month exists")
        copy_inputs(p,prev);p.refresh_from_db()
    elif action=="sync_leave" and p.status==p.OPEN:
        first=date(p.year,p.month,1);last=date(p.year,p.month,calendar.monthrange(p.year,p.month)[1])
        for emp in eligible_employees(p.company,p.year,p.month):
            days=Decimal(0)
            for lr in LeaveRequest.objects.filter(employee=emp,status="approved",leave_type__is_paid=False,start_date__lte=last,end_date__gte=first):
                days+=sum((Decimal("0.5") if lr.half_day else Decimal(1) for d in workdays(emp.company,max(first,lr.start_date),min(last,lr.end_date))),Decimal(0))
            inp,_=PayrollInput.objects.get_or_create(period=p,employee=emp);inp.no_pay_days=days;inp.save()
    elif action=="sync_attendance" and p.status==p.OPEN:
        for inp in p.inputs.select_related("employee"):
            hours=Decimal(0)
            sessions=Attendance.objects.filter(employee=inp.employee,date__year=p.year,date__month=p.month,check_out__isnull=False).select_related("roster__shift")
            for session in sessions:
                if session.roster_id:
                    hours+=max(Decimal(0),Decimal(str(session.worked_hours))-session.roster.shift.expected_hours)
            inp.ot_hours=hours;inp.save()
    elif action=="paid" and p.status==p.LOCKED and p.payment_status!="paid":
        if not data.get("reference", "").strip(): raise ValidationError("Payment reference is required")
        p.payment_status="paid";p.payment_reference=data["reference"];p.paid_at=timezone.now()
    elif action=="statutory" and p.status==p.LOCKED:
        if not data.get("reference", "").strip(): raise ValidationError("Submission reference is required")
        p.statutory_reference=data["reference"]
    else: raise ValidationError("Action is unavailable for your role or this payroll state")
    p.save();audit(user,"payroll."+action,p,before)
    return p

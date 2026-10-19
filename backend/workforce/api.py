"""Session-authenticated API. All scopes and workflow decisions live on the server."""
import csv
import hashlib
import io
import json
import secrets
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps
from pathlib import Path
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.mail import send_mail, EmailMessage
from django.db import transaction, IntegrityError
from django.db.models import Q, Sum
from django.forms.models import model_to_dict
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from core.models import Company, Employee, User, SalaryHistory, SiteTheme
from core.access import visible_employees
from leave.models import LeaveType, LeaveEntitlement, LeaveRequest, HRRequest, leave_balances
from payroll.models import PayrollPeriod, PayrollInput, Payslip, start_period, eligible_employees
from .models import *
from .services import *

# No arbitrary model/field access. Workflow fields cannot be changed with generic CRUD.
RESOURCES = {
 'companies': (Company, ['name','code','address','email','phone','working_weekdays','payday','no_pay_divisor','ot_hourly_divisor','ot_multiplier','payroll_cutoff_day','epf_zone','epf_employer_no','epf_reg_no','etf_reg_no','tin','is_active']),
 'employees': (Employee, ['company','emp_no','full_name','nic','date_of_birth','address','phone','email','designation','department','join_date','leave_date','status','manager','emergency_contact']),
 'payroll-settings': (Employee, ['bank_name','bank_branch','bank_account','epf_no','epf_eligible','apit_applicable','surname','initials','epf_occupation_grade','notes']),
 'shifts': (Shift,['company','name','start_time','end_time','grace_minutes','expected_hours']),
 'rosters': (Roster,['employee','shift','date']),
 'holidays': (Holiday,['company','date','name']),
 'attendance': (Attendance,[]),
 'corrections': (AttendanceCorrection,['attendance','requested_in','requested_out','reason']),
 'leave': (LeaveRequest,['leave_type','start_date','end_date','half_day','reason']),
 'leave-types': (LeaveType,['company','code','name','days_per_year','is_paid','has_limit']),
 'entitlements': (LeaveEntitlement,['employee','leave_type','year','days']),
 'requests': (HRRequest,['employee','category','subject','details','amount']),
 'announcements': (Announcement,['company','title','body']),
 'documents': (Document,['employee','title','kind','file','expires_on']),
 'loans': (Loan,['employee','kind','principal','installment','start_date','reason']),
 'assets': (Asset,['company','employee','name','serial_number','issued_on','returned_on','condition']),
 'checklists': (ChecklistItem,['employee','category','title','due_date','completed']),
 'policies': (PayrollPolicy,['company','name','effective_date','employee_epf','employer_epf','employer_etf','annual_relief','bands','reviewed','source_note']),
 'payroll': (PayrollPeriod,['company','year','month']),
 'inputs': (PayrollInput,['no_pay_days','ot_hours','bonus','epf_earnings','other_earnings','salary_advance','welfare','loan_recovery','other_deductions','apit_override','tax_note','remarks']),
 'payslips': (Payslip,[]),
 'salaries': (SalaryHistory,['employee','effective_date','basic_salary','epf_allowance','fixed_allowance','reason']),
 'audit': (AuditEvent,[]),
 'notifications': (Notification,[]),
}
HR_ONLY={'payroll-settings','companies','employees','shifts','rosters','holidays','leave-types','entitlements','assets','checklists','policies','payroll','inputs','salaries'}
MANAGER_READ={'employees','shifts','rosters','holidays','attendance','corrections','leave','requests','announcements','checklists','notifications'}
EMPLOYEE_READ={'employees','rosters','holidays','attendance','corrections','leave','leave-types','requests','announcements','documents','loans','checklists','payslips','notifications'}
READ_ONLY={'attendance','payslips','audit','notifications'}

def error(message, status=400): return JsonResponse({'error':message},status=status)
def body(request):
    if request.content_type and request.content_type.startswith('multipart/'): return request.POST.copy()
    try: return json.loads(request.body or '{}')
    except (ValueError,UnicodeDecodeError): raise ValidationError('Invalid JSON')

def endpoint(public=False):
    def deco(fn):
        @wraps(fn)
        def wrapped(request,*a,**kw):
            try:
                if not public:
                    if not request.user.is_authenticated: return error('Please sign in',401)
                    if request.user.must_change_password: return error('Change your temporary password first',428)
                    if request.user.company_id and not request.user.company.is_active: raise PermissionDenied('Company is inactive')
                return fn(request,*a,**kw)
            except PermissionDenied as exc: return error(str(exc) or 'Access denied',403)
            except (Http404, Employee.DoesNotExist, PayrollPeriod.DoesNotExist, LeaveRequest.DoesNotExist): return error('Not found',404)
            except ValidationError as exc: return error('; '.join(exc.messages))
            except (ValueError, TypeError, KeyError, IntegrityError) as exc: return error('Invalid or conflicting data. Check required fields and unique values.')
        return wrapped
    return deco

def user_json(u):
    return {'id':u.pk,'username':u.username,'name':u.get_full_name() or u.username,'role':'admin' if u.is_hr_admin else u.role,
            'company_id':u.company_id,'employee_id':u.employee_id,'must_change_password':u.must_change_password,
            'theme':u.company.theme() if u.company_id else SiteTheme.current().theme(),
            'logo':u.company.logo.url if u.company_id and u.company.logo else None}

@endpoint(public=True)
@ensure_csrf_cookie
@require_http_methods(['GET','POST'])
def auth(request, action):
    data=body(request) if request.method=='POST' else {}
    if action=='session' and request.method=='GET':
        return JsonResponse({'user':user_json(request.user) if request.user.is_authenticated else None,'csrf':get_token(request)})
    if request.method!='POST': return error('POST required',405)
    if action=='login':
        ip=request.META.get('REMOTE_ADDR','unknown')
        key='login:'+hashlib.sha256((ip+str(data.get('username','')).lower()).encode()).hexdigest()
        ipkey='login-ip:'+ip
        if cache.get(key,0)>=8 or cache.get(ipkey,0)>=40: return error('Too many attempts. Try again in 15 minutes.',429)
        u=authenticate(request,username=data.get('username'),password=data.get('password'))
        if not u or (u.company_id and not u.company.is_active):
            cache.set(key,cache.get(key,0)+1,900);cache.set(ipkey,cache.get(ipkey,0)+1,900)
            return error('Invalid username or password',401)
        cache.delete(key);login(request,u)
        return JsonResponse({'user':user_json(u),'csrf':get_token(request)})
    if action=='logout': logout(request);return JsonResponse({'ok':True})
    if action=='password':
        if not request.user.is_authenticated: return error('Please sign in',401)
        if not request.user.check_password(data.get('old_password','')): raise ValidationError('Current password is incorrect')
        validate_password(data.get('password',''),request.user)
        request.user.set_password(data['password']);request.user.must_change_password=False;request.user.save()
        update_session_auth_hash(request,request.user)
        return JsonResponse({'user':user_json(request.user),'csrf':get_token(request)})
    if action=='reset-request':
        key='reset:'+request.META.get('REMOTE_ADDR','unknown')
        if cache.get(key,0)>=5:return error('Please try again later',429)
        cache.set(key,cache.get(key,0)+1,900)
        for u in User.objects.filter(email__iexact=data.get('email',''),is_active=True).exclude(email=''):
            url=f'{settings.PUBLIC_URL}/reset/{urlsafe_base64_encode(force_bytes(u.pk))}/{default_token_generator.make_token(u)}'
            send_mail('Reset your HR password',f'Open this link to reset your password: {url}',settings.DEFAULT_FROM_EMAIL,[u.email])
        return JsonResponse({'message':'If an active account matches, a reset email has been sent.'})
    if action=='reset-confirm':
        try:u=User.objects.get(pk=force_str(urlsafe_base64_decode(data.get('uid',''))),is_active=True)
        except Exception:raise ValidationError('Invalid reset link')
        if not default_token_generator.check_token(u,data.get('token','')):raise ValidationError('Reset link expired or invalid')
        validate_password(data.get('password',''),u);u.set_password(data['password']);u.must_change_password=False;u.save()
        return JsonResponse({'ok':True})
    if action=='accept-invite':
        with transaction.atomic():
            invitation=Invitation.objects.select_for_update().filter(token_hash=hashlib.sha256(data.get('token','').encode()).hexdigest(),used_at__isnull=True,expires_at__gt=timezone.now()).first()
            if not invitation:raise ValidationError('Invitation expired or already used')
            emp=invitation.employee
            if emp.status!=Employee.ACTIVE or not emp.company.is_active:raise ValidationError('Employee is inactive')
            username=data.get('username','').strip()
            if not username:raise ValidationError('Username is required')
            u=User(username=username,email=emp.email,employee=emp,company=emp.company,role='employee',must_change_password=False)
            validate_password(data.get('password',''),u);u.set_password(data['password']);u.full_clean();u.save()
            invitation.used_at=timezone.now();invitation.save()
        return JsonResponse({'ok':True})
    return error('Unknown authentication action',404)

def companies(u): return Company.objects.all() if u.is_hr_admin else Company.objects.filter(pk=u.company_id)

def scope(u,name):
    model,_=RESOURCES[name]
    if not (u.is_hr_admin or u.is_client_hr):
        allowed=MANAGER_READ if u.role=='manager' else EMPLOYEE_READ
        if name not in allowed:raise PermissionDenied
    qs=model.objects.all()
    emps=visible_employees(u)
    if name=='companies':return companies(u)
    if name in ('employees','payroll-settings'):return emps
    if name=='notifications':return qs.filter(user=u)
    if name=='audit':return qs if u.is_hr_admin else qs.filter(company_id=u.company_id)
    if name=='inputs':return qs.filter(period__company__in=companies(u))
    if name=='payslips':
        qs=qs.filter(period__company__in=companies(u))
        if not (u.is_hr_admin or u.is_client_hr):qs=qs.filter(employee_id=u.employee_id,period__status__in=['approved','locked'])
        return qs
    names={f.name for f in model._meta.fields}
    if 'company' in names:return qs.filter(company__in=companies(u))
    if 'employee' in names:return qs.filter(employee__in=emps)
    return qs.none()

def label(obj):
    if isinstance(obj,Employee):return f'{obj.emp_no} · {obj.full_name}'
    if isinstance(obj,User):return obj.get_full_name() or obj.username
    if isinstance(obj,Attendance):return f'{obj.date} · {obj.employee.full_name}'
    if isinstance(obj,PayrollPeriod):return str(obj)
    return str(getattr(obj,'name',None) or getattr(obj,'title',None) or obj)

def serialize(obj,u):
    d={}
    for f in obj._meta.fields:
        if f.name in ('token_hash','password'):continue
        if isinstance(f,models.FileField):
            d[f.name]=f'/api/files/{obj.pk}/' if getattr(obj,f.name) else ''
        else:d[f.name]=getattr(obj,f.attname)
        if isinstance(f,models.ForeignKey):
            related=getattr(obj,f.name,None)
            d[f.name+'_label']=label(related) if related else ''
    if isinstance(obj,Employee) and not (u.is_hr_admin or u.is_client_hr):
        d.pop('notes',None)
        if u.role=='manager':
            for k in ['basic_salary','epf_allowance','fixed_allowance','bank_account','bank_name','bank_branch','nic','address','date_of_birth','emergency_contact']:d.pop(k,None)
    if isinstance(obj,Attendance):
        d['worked_hours']=obj.worked_hours;d['on_break']=obj.breaks.filter(end__isnull=True).exists()
        d['breaks']=[{'start':b.start,'end':b.end} for b in obj.breaks.all()]
    if isinstance(obj,Loan):d['balance']=obj.balance
    if isinstance(obj,HRRequest):d['messages']=[{'author':label(m.author) if m.author else 'Former user','body':m.body,'created_at':m.created_at} for m in obj.messages.select_related('author')]
    if isinstance(obj,Announcement):d['acknowledged']=Acknowledgement.objects.filter(announcement=obj,user=u).exists();d['acknowledgements']=Acknowledgement.objects.filter(announcement=obj).count()
    if isinstance(obj,Payslip):d['employee_label']=obj.snapshot.get('full_name',d.get('employee_label'));d['print_url']=f'/payslip/{obj.pk}/'
    return d

def form_for(request,name,instance=None):
    model,fields=RESOURCES[name];u=request.user
    fields=list(fields)
    if name=='employees' and instance:
        fields=[f for f in fields if f not in ('company','basic_salary','epf_allowance','fixed_allowance')]
    if name in ('requests','documents','loans') and not (u.is_hr_admin or u.is_client_hr):fields=[f for f in fields if f!='employee']
    data=body(request) if request.method!='GET' else None
    Form=forms.modelform_factory(model,fields=fields)
    form=Form(data,request.FILES or None,instance=instance)
    for field in form.fields.values():
        if not isinstance(field,forms.ModelChoiceField):continue
        m=field.queryset.model
        if m==Company:field.queryset=companies(u)
        elif m==Employee:field.queryset=visible_employees(u)
        elif m==User:field.queryset=User.objects.filter(company__in=companies(u),role='manager',is_active=True)
        elif m==Shift:field.queryset=Shift.objects.filter(company__in=companies(u))
        elif m==LeaveType:field.queryset=LeaveType.objects.filter(company__in=companies(u))
        elif m==Attendance:field.queryset=Attendance.objects.filter(employee_id=u.employee_id)
    return form

def writable(u,name,obj=None):
    if name in READ_ONLY:raise PermissionDenied('Read only')
    if name=='payroll-settings' and obj is None:raise ValidationError('Add the employee under People first')
    if name in HR_ONLY:require_hr(u)
    if name=='companies' and not u.is_hr_admin:raise PermissionDenied('Only system admin manages companies')
    if name=='policies' and not u.is_hr_admin:raise PermissionDenied('Only payroll admin manages policies')
    if name in ('announcements',):require_hr(u)
    if obj and name in ('leave','corrections','loans','requests','payroll','salaries','policies','documents'):
        raise ValidationError('Use the dedicated workflow action; these records cannot be edited directly')
    if name in ('leave','corrections') and not u.employee_id:raise ValidationError('An employee-linked account is required')

@endpoint()
@require_http_methods(['GET','POST'])
def resource(request,name,pk=None):
    if name not in RESOURCES:raise Http404
    qs=scope(request.user,name)
    obj=get_object_or_404(qs,pk=pk) if pk else None
    if request.method=='GET':
        if obj:return JsonResponse({'item':serialize(obj,request.user)})
        if name=='inputs':
            if not request.GET.get('period'):raise ValidationError('Select a payroll period')
            qs=qs.filter(period_id=request.GET['period'])
        for f in ('employee','company','status','year','month'):
            if request.GET.get(f) and f in {x.name for x in qs.model._meta.fields}:qs=qs.filter(**{f:request.GET[f]})
        if request.GET.get('q'):
            text_fields=[f.name for f in qs.model._meta.fields if isinstance(f,(models.CharField,models.TextField))]
            query=Q()
            for f in text_fields:query|=Q(**{f+'__icontains':request.GET['q']})
            qs=qs.filter(query)
        count=qs.count();page=max(1,int(request.GET.get('page',1)));limit=50
        rows=list(qs.order_by('-pk')[(page-1)*limit:page*limit])
        return JsonResponse({'items':[serialize(o,request.user) for o in rows],'count':count,'page':page})
    writable(request.user,name,obj)
    with transaction.atomic():
        if obj and name == "inputs": PayrollPeriod.objects.select_for_update().get(pk=obj.period_id)
        if obj:obj=get_object_or_404(qs.select_for_update(),pk=pk)
        before=plain(obj) if obj else {}
        form=form_for(request,name,obj)
        if not form.is_valid():return JsonResponse({'error':'Please correct the highlighted fields','fields':form.errors.get_json_data()},status=400)
        item=form.save(commit=False)
        u=request.user;data=body(request)
        if name in ('leave','corrections') or (name in ('requests','loans','documents') and not (u.is_hr_admin or u.is_client_hr)):
            if not u.employee_id:raise ValidationError('Employee account required')
            item.employee=u.employee
        if name=='leave':submit_leave(u,item);return JsonResponse({'item':serialize(item,u)},status=201)
        if name=='companies':
            if item.no_pay_divisor<=0 or item.ot_hourly_divisor<=0 or not 1<=item.payday<=28 or not 1<=item.payroll_cutoff_day<=31:raise ValidationError('Invalid payroll calendar or divisors')
            if not isinstance(item.working_weekdays,list) or any(type(d)!=int or d not in range(7) for d in item.working_weekdays):raise ValidationError('Working weekdays must be a JSON list of integers 0–6')
        if name=='employees':
            if obj and (item.join_date!=Employee.objects.get(pk=obj.pk).join_date or item.leave_date!=Employee.objects.get(pk=obj.pk).leave_date):
                if PayrollPeriod.objects.filter(company=item.company,status__in=['approved','locked']).filter(payslips__employee=item).exists() and data.get('status')!='resigned':
                    raise ValidationError('Employment dates affect approved payroll; record an audited payroll adjustment if needed')
            if item.manager_id and item.manager.company_id!=item.company_id:raise ValidationError('Manager must belong to the same company')
            if min(item.basic_salary,item.epf_allowance,item.fixed_allowance)<0:raise ValidationError('Salary cannot be negative')
            if item.leave_date and item.join_date and item.leave_date<item.join_date:raise ValidationError('Leave date precedes joining date')
            if item.status=='resigned' and not item.leave_date:raise ValidationError('Resignation date is required')
        if name=='shifts' and (item.expected_hours<=0 or item.expected_hours>24 or item.start_time==item.end_time):raise ValidationError('Enter distinct start/end times and expected hours between 0 and 24')
        if name=='entitlements' and item.days<0:raise ValidationError('Leave entitlement cannot be negative')
        if name=='leave-types' and item.days_per_year<0:raise ValidationError('Leave allowance cannot be negative')
        if name=='rosters' and item.shift.company_id!=item.employee.company_id:raise ValidationError('Shift belongs to another company')
        if name=='assets' and item.employee_id and item.employee.company_id!=item.company_id:raise ValidationError('Employee belongs to another company')
        if name=='entitlements' and item.leave_type.company_id!=item.employee.company_id:raise ValidationError('Leave type belongs to another company')
        if name=='corrections':
            if item.attendance_id and item.attendance.employee_id!=item.employee_id:raise PermissionDenied
            if item.requested_out<=item.requested_in:raise ValidationError('Check-out must follow check-in')
            if item.requested_out>timezone.now():raise ValidationError('Correction cannot be in the future')
        if name=='documents':
            upload=request.FILES.get('file')
            if not upload:raise ValidationError('Select a document')
            if upload.size>10*1024*1024 or Path(upload.name).suffix.lower() not in ('.pdf','.png','.jpg','.jpeg','.docx'):raise ValidationError('Upload a PDF, image or DOCX up to 10 MB')
            item.uploaded_by=u
        if name=='announcements':item.created_by=u
        if name=='loans':
            if item.principal<=0 or item.installment<=0 or item.installment>item.principal:raise ValidationError('Enter a positive principal and an installment no larger than the principal')
            if item.kind not in ('loan','advance'):raise ValidationError('Kind must be loan or advance')
        if name=='policies':
            if not item.bands or item.bands[-1][0] is not None:raise ValidationError('Tax bands must end with [null, rate]')
            for width,rate in item.bands:
                if (width is not None and Decimal(str(width))<=0) or not 0<=Decimal(str(rate))<=1:raise ValidationError('Invalid tax bands')
            if any(not 0<=v<=1 for v in (item.employee_epf,item.employer_epf,item.employer_etf)):raise ValidationError('Contribution rates must be between 0 and 1')
            if item.annual_relief<0:raise ValidationError('Relief cannot be negative')
            if item.reviewed and not item.source_note.strip():raise ValidationError('Document the source and reviewer before marking the policy reviewed')
        if name=='payroll':
            item,created=start_period(item.company,item.year,item.month,carry_forward=bool(data.get('carry_forward',True)))
        else:
            item.full_clean();item.save()
        if name=='companies':LeaveType.seed_defaults(item)
        if name=='employees':
            if not obj:
                SalaryHistory.objects.create(employee=item,effective_date=item.join_date or timezone.localdate(),basic_salary=item.basic_salary,epf_allowance=item.epf_allowance,fixed_allowance=item.fixed_allowance,reason='Opening salary')
                for title in ('Collect signed contract','Verify bank details','Issue equipment','Complete induction'):
                    ChecklistItem.objects.create(employee=item,title=title)
            if item.status=='resigned':
                User.objects.filter(employee=item).update(is_active=False)
                for title in ('Return assigned assets','Complete handover','Review final settlement'):
                    ChecklistItem.objects.get_or_create(employee=item,category='offboarding',title=title)
        if name=='salaries':
            Employee.objects.select_for_update().get(pk=item.employee_id)
            if min(item.basic_salary,item.epf_allowance,item.fixed_allowance)<0:raise ValidationError('Salary cannot be negative')
            if PayrollPeriod.objects.filter(company=item.employee.company,status__in=['processed','approved','locked']).filter(Q(year__gt=item.effective_date.year)|Q(year=item.effective_date.year,month__gte=item.effective_date.month)).exists():raise ValidationError('This effective date overlaps processed payroll; reopen it first, or use a later-period adjustment for locked payroll')
            if item.effective_date<=timezone.localdate():
                latest=item.employee.salary_history.filter(effective_date__lte=timezone.localdate()).order_by('-effective_date','-pk').first()
                Employee.objects.filter(pk=item.employee_id).update(basic_salary=latest.basic_salary,epf_allowance=latest.epf_allowance,fixed_allowance=latest.fixed_allowance)
        audit(u,name+'.save',item,before)
        if name in ('requests','corrections','loans'):notify_hr(item.employee,f'{name.title()} submitted for {item.employee.full_name}');notify(item.employee,f'{name.title()} updated')
        if name=='announcements':
            for account in User.objects.filter(company=item.company,is_active=True):Notification.objects.create(user=account,text=item.title)
        return JsonResponse({'item':serialize(item,u)},status=200 if obj else 201)

@endpoint()
@require_http_methods(['GET'])
def schema(request,name,pk=None):
    if name not in RESOURCES:raise Http404
    scope(request.user,name)
    obj=get_object_or_404(scope(request.user,name),pk=pk) if pk else None
    writable(request.user,name,obj)
    form=form_for(request,name,obj)
    out=[]
    for key,f in form.fields.items():
        typ='text';options=None
        if isinstance(f,forms.ModelChoiceField):typ='select';options=[{'value':o.pk,'label':label(o)} for o in f.queryset[:2000]]
        elif isinstance(f,forms.ChoiceField):typ='select';options=[{'value':v,'label':str(l)} for v,l in f.choices]
        elif isinstance(f,forms.BooleanField):typ='checkbox'
        elif isinstance(f,forms.DateTimeField):typ='datetime-local'
        elif isinstance(f,forms.DateField):typ='date'
        elif isinstance(f,forms.TimeField):typ='time'
        elif isinstance(f,(forms.DecimalField,forms.IntegerField)):typ='number'
        elif isinstance(f,forms.FileField):typ='file'
        elif isinstance(f,forms.JSONField):typ='json'
        elif isinstance(f.widget,forms.Textarea):typ='textarea'
        initial=form.initial.get(key,f.initial)
        if callable(initial):initial=initial()
        if typ=='json':initial=json.dumps(initial if initial is not None else [])
        out.append({'name':key,'label':str(f.label),'type':typ,'required':f.required,'help':str(f.help_text),'options':options,'initial':initial})
    return JsonResponse({'fields':out})

@endpoint()
@require_http_methods(['POST'])
def action(request,name,pk,verb):
    data=body(request);u=request.user
    if name not in RESOURCES:raise Http404
    with transaction.atomic():
        obj=get_object_or_404(scope(u,name).select_for_update(),pk=pk)
        if name=='payroll':payroll_action(u,obj.pk,verb,data)
        elif name=='leave' and verb in ('approve','reject'):decide_leave(u,obj.pk,verb,data.get('comment',''))
        elif name=='leave' and verb=='cancel':
            if obj.employee_id!=u.employee_id or obj.status!='pending':raise PermissionDenied
            obj.status='cancelled';obj.save();audit(u,'leave.cancel',obj)
        elif name=='corrections' and verb in ('approve','reject'):correct_attendance(u,obj,verb=='approve')
        elif name=='announcements' and verb=='acknowledge':Acknowledgement.objects.get_or_create(announcement=obj,user=u)
        elif name=='notifications' and verb=='read':obj.read=True;obj.save()
        elif name=='requests' and verb=='reply':
            message=data.get('message','').strip()
            if not message:raise ValidationError('Write a message')
            RequestMessage.objects.create(request=obj,author=u,body=message)
            if data.get('status'):
                if u.role not in ('admin','client_hr','manager') and not u.is_superuser:raise PermissionDenied
                if data['status'] not in ('open','in_progress','done','declined'):raise ValidationError('Invalid status')
                obj.status=data['status'];obj.handled_by=u;obj.response=message;obj.save()
            notify(obj.employee,f'Reply: {obj.subject}');notify_hr(obj.employee,f'Updated request: {obj.subject}');audit(u,'request.reply',obj)
        elif name=='loans' and verb in ('approve','reject'):
            require_hr(u)
            if obj.employee_id==u.employee_id:raise PermissionDenied('Another approver must review your loan')
            if obj.status!='pending':raise ValidationError('Already decided')
            obj.status='approved' if verb=='approve' else 'rejected';obj.approved_by=u;obj.save();audit(u,'loan.'+verb,obj);notify(obj.employee,f'Loan request {obj.status}')
        elif name=='payslips' and verb=='email':
            from .reports import payslip_pdf
            require_hr(u)
            if obj.period.status not in ('approved','locked'):raise ValidationError('Approve payroll first')
            address=obj.snapshot.get('email')
            if not address:raise ValidationError('No email in the approved snapshot')
            message=EmailMessage(f'Payslip · {obj.period.label}','Your payslip is attached.',settings.DEFAULT_FROM_EMAIL,[address])
            message.attach(f'payslip-{obj.pk}.pdf',payslip_pdf(obj),'application/pdf');message.send()
            obj.emailed_at=timezone.now();obj.save(update_fields=['emailed_at']);audit(u,'payslip.email',obj)
        elif name=='employees' and verb=='invite':
            require_hr(u)
            if User.objects.filter(employee=obj).exists():raise ValidationError('Employee already has an account; use password reset')
            if not obj.email:raise ValidationError('Add the employee email first')
            token=secrets.token_urlsafe(32)
            Invitation.objects.filter(employee=obj,used_at__isnull=True).update(used_at=timezone.now())
            Invitation.objects.create(employee=obj,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(days=2))
            send_mail('Your HR invitation',f'Create your account: {settings.PUBLIC_URL}/invite/{token}',settings.DEFAULT_FROM_EMAIL,[obj.email])
            audit(u,'employee.invite',obj)
        elif name=='employees' and verb=='account':
            if not u.is_hr_admin:raise PermissionDenied('Only system admin can grant HR/manager roles')
            role=data.get('role','employee')
            if role not in ('employee','manager','client_hr'):raise ValidationError('Invalid role')
            account=User.objects.filter(employee=obj).first()
            if not account:raise ValidationError('Employee must accept their invitation first')
            account.role=role;account.save();audit(u,'account.role',account)
        elif name=='checklists' and verb=='complete':
            require_hr(u);obj.completed=True;obj.save();audit(u,'checklist.complete',obj)
        else:raise ValidationError('Unknown action')
    return JsonResponse({'ok':True})

@endpoint()
@require_http_methods(['POST'])
def attendance_clock(request,verb):
    return JsonResponse({'item':serialize(clock(request.user,verb),request.user)})

@endpoint()
@require_http_methods(['GET'])
def dashboard(request):
    u=request.user;emps=visible_employees(u);today=timezone.localdate()
    periods=PayrollPeriod.objects.filter(company__in=companies(u))
    stats={'employees':emps.filter(status='active').count(),'present':Attendance.objects.filter(employee__in=emps,date=today).values('employee').distinct().count(),
      'pending_leave':LeaveRequest.objects.filter(employee__in=emps,status='pending').count(),'open_requests':HRRequest.objects.filter(employee__in=emps,status__in=['open','in_progress']).count()}
    trend=[]
    if u.is_hr_admin or u.is_client_hr:
        for p in periods.filter(status__in=['approved','locked']).order_by('-year','-month')[:6]:
            trend.append({'label':p.label,'company':p.company.code,'net':p.payslips.aggregate(n=Sum('net_salary'))['n'] or 0})
        stats['payroll_to_review']=periods.exclude(status='locked').count()
    return JsonResponse({'stats':stats,'companies':[{'id':c.pk,'name':c.name,'code':c.code} for c in companies(u)],
       'trend':list(reversed(trend)), 'balances':[{**b,'type':b['type'].name} for b in leave_balances(u.employee,today.year)] if u.employee_id else [],
       'announcements':[serialize(a,u) for a in Announcement.objects.filter(company__in=companies(u)).order_by('-pk')[:4]],
       'active_session':serialize(a,u) if u.employee_id and (a:=Attendance.objects.filter(employee_id=u.employee_id,check_out__isnull=True).first()) else None,
       'unread':Notification.objects.filter(user=u,read=False).count(),
       'expiring_documents':Document.objects.filter(employee__in=emps,expires_on__range=(today,today+timedelta(days=30))).count()})

@endpoint()
@require_http_methods(['GET'])
def file_download(request,pk):
    doc=get_object_or_404(scope(request.user,'documents'),pk=pk)
    audit(request.user,'document.download',doc)
    return FileResponse(doc.file.open('rb'),as_attachment=True,filename=Path(doc.file.name).name)

@endpoint()
@require_http_methods(['GET'])
def report(request,kind,pk):
    from .reports import generate_report
    return generate_report(request,kind,pk)

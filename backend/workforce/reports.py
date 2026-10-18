import csv
import io
from decimal import Decimal
from html import escape
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from core.models import Employee
from payroll.models import PayrollPeriod, Payslip
from .services import audit, require_hr


def pdf(title, lines, rows=None):
    stream=io.BytesIO();styles=getSampleStyleSheet()
    story=[Paragraph(escape(title),styles['Title']),Spacer(1,14)]
    for line in lines:story.extend([Paragraph(escape(str(line)),styles['BodyText']),Spacer(1,7)])
    if rows:
        table=Table([[Paragraph(escape(str(c)),styles['BodyText']) for c in row] for row in rows],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dce9e2')),('GRID',(0,0),(-1,-1),.4,colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]));story.append(table)
    SimpleDocTemplate(stream,pagesize=A4,rightMargin=36,leftMargin=36).build(story)
    return stream.getvalue()


def payslip_pdf(s):
    e=s.frozen_employee;c=s.period.company_snapshot
    fields=[('Basic',s.basic_salary),('EPF allowances',s.epf_allowance),('Other allowances',s.fixed_allowance),('EPF earnings',s.epf_earnings),('Overtime',s.ot_amount),('Bonus',s.bonus),('Other earnings',s.other_earnings),('No-pay deduction',s.no_pay_deduction),('Gross salary',s.gross_salary),('Employee EPF',s.epf_employee),('APIT',s.apit),('Advance',s.salary_advance),('Loan recovery',s.loan_recovery),('Welfare',s.welfare),('Other deductions',s.other_deductions),('Net salary',s.net_salary),('Employer EPF',s.epf_employer),('Employer ETF',s.etf_employer)]
    return pdf(f'Payslip · {s.period.label}',[c.get('name',s.period.company.name),f'{e.emp_no} · {e.full_name}',e.designation,f'Bank: {e.bank_name} · account ending {e.bank_account[-4:]}'],[['Description','LKR']]+[[k,f'{v:,.2f}'] for k,v in fields])


def safe_cell(v):
    s=str(v or '')
    return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s


def generate_report(request,kind,pk):
    from .api import scope
    u=request.user
    if kind=='payslip':
        s=get_object_or_404(scope(u,'payslips'),pk=pk)
        if s.period.status not in ('approved','locked'):raise ValidationError('Approve payroll first')
        data=payslip_pdf(s);filename=f'payslip-{s.period.year}-{s.period.month}-{s.employee.emp_no}.pdf'
    elif kind in ('salary-letter','service-letter'):
        require_hr(u);e=get_object_or_404(scope(u,'employees'),pk=pk)
        data=pdf('Salary confirmation' if kind=='salary-letter' else 'Employment confirmation',[e.company.name,e.company.address,f'Date: {timezone.localdate()}',f'To whom it may concern,',f'This confirms that {e.full_name} (employee {e.emp_no}) joined our company on {e.join_date or "[join date not recorded]"} as {e.designation or "[designation not recorded]"}.',f'Employment status: {e.get_status_display()}.']+([f'Current recorded monthly fixed remuneration: LKR {e.total_fixed_pay:,.2f}.'] if kind=='salary-letter' else [])+['Prepared for HR review and authorized signature.','Authorized signatory: _______________________'])
        filename=f'{kind}-{e.emp_no}.pdf';audit(u,'letter.generate',e)
    elif kind=='bank':
        require_hr(u);p=get_object_or_404(scope(u,'payroll'),pk=pk)
        if p.status!='locked':raise ValidationError('Lock payroll before producing the bank schedule')
        output=io.StringIO();writer=csv.writer(output);writer.writerow(['Employee number','Name','Bank','Branch','Account','Amount LKR','Reference'])
        for s in p.payslips.all():
            e=s.frozen_employee
            if not e.bank_account:raise ValidationError(f'Missing bank account in approved snapshot for {e.full_name}; correct via a new payroll revision before locking')
            writer.writerow([safe_cell(e.emp_no),safe_cell(e.full_name),safe_cell(e.bank_name),safe_cell(e.bank_branch),safe_cell(e.bank_account),str(s.net_salary),f'{p.year}-{p.month:02d}'])
        response=HttpResponse(output.getvalue(),content_type='text/csv');response['Content-Disposition']=f'attachment; filename="bank-schedule-{p.pk}.csv"';audit(u,'bank-schedule.export',p);return response
    elif kind=='annual':
        require_hr(u);e=get_object_or_404(scope(u,'employees'),pk=pk);year=int(request.GET.get('year',timezone.localdate().year))
        slips=e.payslips.filter(period__year=year,period__status__in=['approved','locked']).select_related('period').order_by('period__month')
        rows=[['Month','Gross','EPF','APIT','Net']]
        for s in slips:rows.append([s.period.label,f'{s.gross_salary:,.2f}',f'{s.epf_employee:,.2f}',f'{s.apit:,.2f}',f'{s.net_salary:,.2f}'])
        data=pdf(f'Annual earnings statement · {year}',[e.company.name,e.full_name,'Internal calendar-year summary. This is not an official T-10 certificate.'],rows);filename=f'annual-{e.emp_no}-{year}.pdf'
    elif kind=='attendance':
        require_hr(u);e=get_object_or_404(scope(u,'employees'),pk=pk)
        start=request.GET.get('start',f'{timezone.localdate():%Y-%m}-01');end=request.GET.get('end',str(timezone.localdate()))
        from .models import Attendance
        rows=[['Date','Check in','Check out','Hours','Late min']]
        for a in Attendance.objects.filter(employee=e,date__range=(start,end)).order_by('date'):
            rows.append([str(a.date),timezone.localtime(a.check_in).strftime('%H:%M'),timezone.localtime(a.check_out).strftime('%H:%M') if a.check_out else 'Open',a.worked_hours,a.late_minutes])
        data=pdf('Attendance report',[e.full_name,f'{start} to {end}'],rows);filename=f'attendance-{e.emp_no}.pdf'
    elif kind=='variance':
        require_hr(u);p=get_object_or_404(scope(u,'payroll'),pk=pk);prev=p.previous()
        old={s.employee_id:s for s in prev.payslips.all()} if prev else {}
        rows=[['Employee','Previous net','Current net','Change']]
        for s in p.payslips.all():
            oldnet=old[s.employee_id].net_salary if s.employee_id in old else Decimal(0)
            rows.append([s.frozen_employee.full_name,f'{oldnet:,.2f}',f'{s.net_salary:,.2f}',f'{s.net_salary-oldnet:,.2f}'])
        data=pdf('Payroll variance',[p.company.name,p.label,'Comparison with most recent earlier payroll period.'],rows);filename=f'variance-{p.pk}.pdf'
    else:raise ValidationError('Unknown report')
    resp=HttpResponse(data,content_type='application/pdf');resp['Content-Disposition']=f'attachment; filename="{filename}"';return resp

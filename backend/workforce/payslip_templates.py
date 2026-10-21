"""Company-branded output of approved payroll snapshots; no payroll recalculation."""
import calendar
import io
from datetime import date
from decimal import Decimal
from html import escape
from django.core.exceptions import ValidationError
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

TEMPLATES={'navy':('Navy & teal','#172b4d','#0f766e'),'classic':('Classic gold','#25271f','#a87523')}

def select_template(s,template=None):
    choice=template or getattr(s.period.company,'payslip_template','navy')
    if choice not in TEMPLATES:raise ValidationError('Select Navy & teal or Classic gold')
    return choice

def figures(s):
    """No-pay is shown explicitly as a deduction so gross display reconciles."""
    earnings=[('BASIC SALARY',s.basic_salary),('EPF-ABLE ALLOWANCES',s.epf_allowance),('FIXED ALLOWANCE',s.fixed_allowance),('OTHER EPF-ABLE EARNINGS',s.epf_earnings),('OVERTIME',s.ot_amount),('BONUS',s.bonus),('OTHER EARNINGS',s.other_earnings)]
    template=getattr(s,'snapshot',{}).get('salary_template')
    if template:
        earnings=[('BASIC SALARY',s.basic_salary)]+[(a['name'],Decimal(a['amount'])) for a in template['allowances']]+earnings[3:]
    deductions=[('LEAVE / NO-PAY',s.no_pay_deduction),('ADV. PERSONAL INCOME TAX',s.apit),('EPF - EMPLOYEE',s.epf_employee),('WELFARE',s.welfare),('SALARY ADVANCE',s.salary_advance),('LOAN RECOVERY',s.loan_recovery),('OTHER DEDUCTIONS',s.other_deductions)]
    gross=sum((Decimal(v) for _,v in earnings),Decimal(0))
    total_deductions=Decimal(s.total_deductions)+Decimal(s.no_pay_deduction)
    if abs(gross-total_deductions-Decimal(s.net_salary))>Decimal('.01'):
        raise ValidationError('Payslip amounts do not reconcile; review the saved payroll before exporting')
    return earnings,deductions,gross,total_deductions

def slip_story(s,template):
    _,dark,accent=TEMPLATES[template];dark=colors.HexColor(dark);accent=colors.HexColor(accent)
    normal=ParagraphStyle('body',fontName='Helvetica',fontSize=9,leading=13,textColor=colors.HexColor('#1e293b'))
    bold=ParagraphStyle('bold',parent=normal,fontName='Helvetica-Bold')
    light=ParagraphStyle('light',parent=normal,textColor=colors.white,fontSize=9)
    heading=ParagraphStyle('heading',parent=light,fontName='Helvetica-Bold',fontSize=18,leading=22)
    def p(v,style=normal):return Paragraph(escape(str(v or '')).replace('\n','<br/>'),style)
    def money(v):return f'{Decimal(v):,.2f}' if Decimal(v) else '-'
    e=s.frozen_employee;c=s.period.company_snapshot or {};name=c.get('name',s.period.company.name)
    contacts='\n'.join(str(c[k]) for k in ('phone','email','address') if c.get(k))
    header=Table([[p(name,heading),p(contacts,light)]],colWidths=[290,225])
    header.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),dark),('LINEBELOW',(0,0),(-1,-1),5,accent),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),16),('RIGHTPADDING',(0,0),(-1,-1),16),('TOPPADDING',(0,0),(-1,-1),18),('BOTTOMPADDING',(0,0),(-1,-1),18)]))
    last=date(s.period.year,s.period.month,calendar.monthrange(s.period.year,s.period.month)[1])
    meta=Table([[p(last.strftime('%d.%m.%Y'),bold),p(e.full_name,bold)],[p(f'PAY SLIP FOR: {last:%b %Y}'.upper(),bold),p(e.designation)],[p(f'EMPLOYEE NUMBER: {e.emp_no}',bold),p('Currency: LKR')]],colWidths=[270,245])
    meta.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    earnings,deductions,gross,total=figures(s)
    rows=[];lines=[]
    def group(title,items,total_label=None,total_value=None):
        shown=[(k,v) for k,v in items if Decimal(v)!=0 or k in ('BASIC SALARY','FIXED ALLOWANCE','EPF - EMPLOYEE','WELFARE','ADV. PERSONAL INCOME TAX')]
        for i,(k,v) in enumerate(shown):rows.append([p(title if i==0 else '',bold),p(k),p(money(v),ParagraphStyle('amount',parent=normal,alignment=TA_RIGHT))])
        if total_label:
            rows.append(['',p(total_label,bold),p(money(total_value),ParagraphStyle('total',parent=bold,alignment=TA_RIGHT))]);lines.append(len(rows)-1)
        rows.append(['','',''])
    group('EARNINGS',earnings,'TOTAL EARNINGS',gross)
    group('DEDUCTIONS',deductions,'TOTAL DEDUCTIONS',total)
    net_index=len(rows);rows.append(['',p('NET PAY',bold),p(money(s.net_salary),ParagraphStyle('net',parent=bold,alignment=TA_RIGHT))]);rows.append(['','',''])
    group('COMP. CONTRIBUTIONS',[('EPF - EMPLOYER',s.epf_employer),('ETF - EMPLOYER',s.etf_employer)])
    table=Table(rows,colWidths=[148,267,100])
    cmds=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),('BACKGROUND',(0,net_index),(-1,net_index),colors.HexColor('#f1f5f9')),('LINEABOVE',(1,net_index),(-1,net_index),1,accent),('LINEBELOW',(1,net_index),(-1,net_index),1,accent)]
    for i in lines:cmds.append(('LINEABOVE',(2,i),(2,i),.6,dark))
    table.setStyle(TableStyle(cmds))
    account_name=getattr(e,'bank_account_name','') or e.full_name
    bank=Table([[p('Credited To A/C',bold),p(e.bank_account or 'Not recorded')],[p('Account Name',bold),p(account_name)],[p('Bank',bold),p(e.bank_name or 'Not recorded')],[p('Branch Office',bold),p(e.bank_branch or 'Not recorded')]],colWidths=[148,367])
    bank.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    return [header,Spacer(1,28),meta,Spacer(1,22),table,Spacer(1,20),KeepTogether([bank])]

def render_payslips(slips,template=None):
    slips=list(slips)
    if not slips:raise ValidationError('No payslips in this approved period')
    story=[]
    for i,s in enumerate(slips):
        if s.period.status not in ('approved','locked'):raise ValidationError('Approve payroll before exporting payslips')
        if i:story.append(PageBreak())
        story.extend(slip_story(s,select_template(s,template)))
    stream=io.BytesIO()
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawCentredString(A4[0]/2,35,'This payslip is computer-generated and does not require a signature.')
        canvas.drawRightString(A4[0]-40,20,f'Page {doc.page}');canvas.restoreState()
    SimpleDocTemplate(stream,pagesize=A4,leftMargin=40,rightMargin=40,topMargin=28,bottomMargin=55,title='Employee payslip',author='HR Payroll').build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()

from decimal import Decimal as D
from types import SimpleNamespace as NS
from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from .payslip_templates import figures, render_payslips, select_template


def example():
    fields='basic_salary epf_allowance fixed_allowance epf_earnings ot_amount bonus other_earnings no_pay_deduction apit epf_employee welfare salary_advance loan_recovery other_deductions total_deductions net_salary epf_employer etf_employer'.split()
    s=NS(**dict.fromkeys(fields,D(0)))
    s.basic_salary=D(30000);s.fixed_allowance=D(30000);s.epf_employee=D(2400);s.welfare=D(500)
    s.total_deductions=D(2900);s.net_salary=D(57100);s.epf_employer=D(3600);s.etf_employer=D(900)
    s.period=NS(status='approved',year=2026,month=7,company=NS(name='Demo Company',payslip_template='navy'),company_snapshot={'name':'Demo Company','email':'payroll@example.invalid','address':'Example office, Sri Lanka'})
    s.frozen_employee=NS(full_name='Example Employee',designation='Executive',emp_no='DEMO-01',bank_account='DEMO ACCOUNT',bank_account_name='Example Employee',bank_name='Example Bank',bank_branch='Example Branch')
    return s


class PayslipTemplateTests(SimpleTestCase):
    def test_totals_and_no_pay_once(self):
        s=example();self.assertEqual(figures(s)[2:],(D(60000),D(2900)))
        s.no_pay_deduction=D(1000);s.net_salary-=D(1000)
        self.assertEqual(figures(s)[2:],(D(60000),D(3900)))
    def test_reject_inconsistent_totals(self):
        s=example();s.net_salary+=1
        with self.assertRaises(ValidationError):figures(s)
    def test_template_allowlist_and_default(self):
        s=example();self.assertEqual(select_template(s),'navy')
        with self.assertRaises(ValidationError):render_payslips([s],'unknown')
    def test_approval_required(self):
        s=example();s.period.status='open'
        with self.assertRaises(ValidationError):render_payslips([s])
    def test_both_formats_and_escaped_names(self):
        s=example();s.frozen_employee.full_name='Example <Employee> & Co'
        for template in ('navy','classic'):
            self.assertTrue(render_payslips([s,s],template).startswith(b'%PDF'))

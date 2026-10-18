from datetime import date
from core.models import Company
from .models import PayrollPolicy
BANDS=[[1000000,'0.06'],[500000,'0.18'],[500000,'0.24'],[500000,'0.30'],[None,'0.36']]
def company(**kwargs):
    c=Company.objects.create(**kwargs)
    PayrollPolicy.objects.create(company=c,name='Test fixture policy',effective_date=date(2020,1,1),reviewed=True,source_note='Automated test fixture only',bands=BANDS)
    return c

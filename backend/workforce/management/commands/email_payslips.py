from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from payroll.models import Payslip
from workforce.reports import payslip_pdf
from workforce.models import AuditEvent
class Command(BaseCommand):
    help='Send not-yet-emailed approved payslips. Use --send to transmit; default is dry-run.'
    def add_arguments(self,parser):
        parser.add_argument('--period',type=int,required=True)
        parser.add_argument('--send',action='store_true')
    def handle(self,*args,**options):
        ids=Payslip.objects.filter(period_id=options['period'],period__status__in=['approved','locked'],emailed_at__isnull=True).values_list('pk',flat=True)
        for pk in list(ids):
            with transaction.atomic():
                s=Payslip.objects.select_for_update().get(pk=pk)
                if s.emailed_at:continue
                address=s.snapshot.get('email')
                if not address:self.stderr.write(f'Skipped payslip {pk}: missing email');continue
                if not options['send']:
                    self.stdout.write(f'Would email payslip {pk}');continue
                msg=EmailMessage(f'Payslip · {s.period.label}','Your payslip is attached.',settings.DEFAULT_FROM_EMAIL,[address])
                msg.attach(f'payslip-{pk}.pdf',payslip_pdf(s),'application/pdf');msg.send()
                s.emailed_at=timezone.now();s.save(update_fields=['emailed_at'])
                AuditEvent.objects.create(company=s.period.company,action='payslip.email-job',entity='payroll.Payslip',object_id=str(pk))
                self.stdout.write(f'Sent payslip {pk}')

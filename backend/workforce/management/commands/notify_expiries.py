from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import User
from workforce.models import Document, Notification
class Command(BaseCommand):
    help='Create daily HR notifications for documents expiring within 30 days'
    def handle(self,*args,**options):
        today=timezone.localdate()
        for d in Document.objects.filter(expires_on__range=(today,today+timedelta(days=30))).select_related('employee'):
            text=f'{d.employee.full_name}: {d.title} expires {d.expires_on}'
            for u in User.objects.filter(company=d.employee.company,role='client_hr',is_active=True):
                if not Notification.objects.filter(user=u,text=text,created_at__date=today).exists():Notification.objects.create(user=u,text=text)
        self.stdout.write('Expiry notifications checked.')

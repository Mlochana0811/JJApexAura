from django.db import migrations, models
import django.db.models.deletion
class Migration(migrations.Migration):
    dependencies=[('workforce','0004_salarysheet_archived')]
    operations=[migrations.CreateModel(name='SalaryColumnSettings',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('visibility',models.JSONField(blank=True,default=dict)),('revision',models.PositiveIntegerField(default=1)),('company',models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,to='core.company'))])]

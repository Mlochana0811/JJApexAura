from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('workforce','0003_salarysheet_template_config')]
    operations=[migrations.AddField(model_name='salarysheet',name='archived',field=models.BooleanField(default=False))]

from django.db import migrations,models
import apps.manuals.models
class Migration(migrations.Migration):
    dependencies=[('manuals','0003_organization_scope')]
    operations=[migrations.AlterField(model_name='manualattachment',name='file',field=models.FileField(upload_to=apps.manuals.models.tenant_attachment_path))]

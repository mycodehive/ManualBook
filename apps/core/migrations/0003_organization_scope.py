import django.db.models.deletion
from django.db import migrations, models

def backfill(apps, schema_editor):
    org = apps.get_model('organizations', 'Organization').objects.get(slug='legacy')
    for name in ["SiteConfiguration","AuditEvent"]:
        apps.get_model('core', name).objects.using(schema_editor.connection.alias).filter(organization__isnull=True).update(organization_id=org.pk)

class Migration(migrations.Migration):
    dependencies = [('core', '0002_alter_siteconfiguration_primary_color'), ('organizations','0002_legacy')]
    operations = [
        migrations.AddField(model_name='siteconfiguration', name='organization', field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.AddField(model_name='auditevent', name='organization', field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.RunPython(backfill,migrations.RunPython.noop),
        migrations.AlterField(model_name='siteconfiguration', name='organization', field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.AlterField(model_name='auditevent', name='organization', field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.AlterField(model_name='siteconfiguration',name='id',field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        migrations.AddConstraint(model_name='siteconfiguration',constraint=models.UniqueConstraint(fields=('organization',),name='site_configuration_organization')),
    ]

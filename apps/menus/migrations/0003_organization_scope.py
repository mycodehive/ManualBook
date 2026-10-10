import django.db.models.deletion
from django.db import migrations, models

def backfill(apps, schema_editor):
    org = apps.get_model('organizations', 'Organization').objects.get(slug='legacy')
    for name in ["Menu"]:
        apps.get_model('menus', name).objects.using(schema_editor.connection.alias).filter(organization__isnull=True).update(organization_id=org.pk)

class Migration(migrations.Migration):
    dependencies = [('menus', '0002_default_navigation'), ('organizations','0002_legacy')]
    operations = [
        migrations.AddField(model_name='menu', name='organization', field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.RunPython(backfill,migrations.RunPython.noop),
        migrations.AlterField(model_name='menu', name='organization', field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.AlterField(model_name='menu',name='code',field=models.CharField(max_length=50)),
        migrations.AddConstraint(model_name='menu',constraint=models.UniqueConstraint(fields=('organization','code'),name='menu_organization_code')),
    ]

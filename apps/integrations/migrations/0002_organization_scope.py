import django.db.models.deletion
from django.db import migrations, models

def backfill(apps, schema_editor):
    org = apps.get_model('organizations', 'Organization').objects.get(slug='legacy')
    for name in ["Connection","DataResource","FeatureBinding","ConfigurationRevision"]:
        apps.get_model('integrations', name).objects.using(schema_editor.connection.alias).filter(organization__isnull=True).update(organization_id=org.pk)

class Migration(migrations.Migration):
    dependencies = [('integrations', '0001_initial'), ('organizations','0002_legacy')]
    operations = [
        migrations.AddField(model_name='connection', name='organization', field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.AddField(model_name='dataresource', name='organization', field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.AddField(model_name='featurebinding', name='organization', field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.AddField(model_name='configurationrevision', name='organization', field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.RunPython(backfill,migrations.RunPython.noop),
        migrations.AlterField(model_name='connection', name='organization', field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.AlterField(model_name='dataresource', name='organization', field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.AlterField(model_name='featurebinding', name='organization', field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.AlterField(model_name='configurationrevision', name='organization', field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='organizations.organization')),
        migrations.AlterField(model_name='connection',name='name',field=models.CharField(max_length=120,verbose_name='연결명')),
        migrations.AlterField(model_name='featurebinding',name='feature_code',field=models.CharField(max_length=70,verbose_name='기능 코드')),
        migrations.AddConstraint(model_name='connection',constraint=models.UniqueConstraint(fields=('organization','name'),name='connection_organization_name')),
        migrations.AddConstraint(model_name='featurebinding',constraint=models.UniqueConstraint(fields=('organization','feature_code'),name='binding_organization_feature')),
    ]

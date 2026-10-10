from django.db import migrations, models
import django.db.models.deletion

MODEL_NAMES = ('manualspace','manualnode','manualrevision','approvalrequest','manualattachment','manualfavorite','manualrecentview','manualpermissionassignment')

def scope_legacy(apps,schema_editor):
    org=apps.get_model('organizations','Organization').objects.using(schema_editor.connection.alias).get(slug='legacy')
    for name in MODEL_NAMES:
        apps.get_model('manuals',name)._base_manager.using(schema_editor.connection.alias).filter(organization_id__isnull=True).update(organization_id=org.pk)

class Migration(migrations.Migration):
    dependencies=[('manuals','0002_alter_manualpermissionassignment_action'),('organizations','0002_legacy')]
    operations=[
        migrations.AddField(model_name=name,name='organization',field=models.ForeignKey(null=True,on_delete=django.db.models.deletion.PROTECT,to='organizations.organization'))
        for name in MODEL_NAMES
    ] + [migrations.RunPython(scope_legacy,migrations.RunPython.noop)] + [
        migrations.AlterField(model_name=name,name='organization',field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='organizations.organization'))
        for name in MODEL_NAMES
    ]

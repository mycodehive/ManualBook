from django.conf import settings
from django.db import migrations

def migrate_legacy(apps,schema_editor):
    alias=schema_editor.connection.alias
    Organization=apps.get_model('organizations','Organization')
    Membership=apps.get_model('organizations','Membership')
    OrganizationGroup=apps.get_model('organizations','OrganizationGroup')
    User=apps.get_model(settings.AUTH_USER_MODEL)
    Group=apps.get_model('auth','Group')
    org,_=Organization.objects.using(alias).get_or_create(slug='legacy',defaults={'name':'기존 조직','active':True})
    groups={}
    for group in Group.objects.using(alias).all():
        groups[group.pk]=OrganizationGroup.objects.using(alias).create(organization_id=org.pk,group_id=group.pk,name=group.name)
    for user in User.objects.using(alias).all():
        member,_=Membership.objects.using(alias).get_or_create(organization_id=org.pk,user_id=user.pk,defaults={'role':'admin' if user.is_staff else 'member','active':user.is_active})
        member.groups.set([groups[g.pk] for g in user.groups.using(alias).all()])

class Migration(migrations.Migration):
    dependencies=[('organizations','0001_initial'),('core','0002_alter_siteconfiguration_primary_color'),('menus','0002_default_navigation'),('manuals','0002_alter_manualpermissionassignment_action'),('integrations','0001_initial')]
    operations=[migrations.RunPython(migrate_legacy,migrations.RunPython.noop)]

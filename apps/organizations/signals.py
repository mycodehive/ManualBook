from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .scoping import ScopedModel,current_organization
from .models import OrganizationGroup,Membership

@receiver(m2m_changed,dispatch_uid='manualbook_tenant_m2m_validation')
def validate_tenant_many_to_many(sender,instance,action,reverse,model,pk_set,**kwargs):
    if action not in {'pre_add','pre_remove','pre_clear'}: return
    if not any(field.is_relation and isinstance(field.related_model,type) and issubclass(field.related_model,ScopedModel) for field in sender._meta.fields): return
    org_id=getattr(instance,'organization_id',None)
    if not org_id and isinstance(instance,Group): org_id=OrganizationGroup.all_objects.filter(group=instance).values_list('organization_id',flat=True).first()
    org=current_organization()
    if not org or not org_id or org_id != org.pk: raise ValidationError('그룹·사용자 연결에는 같은 조직 컨텍스트가 필요합니다.')
    if action=='pre_clear' or not pk_set: return
    if isinstance(model,type) and issubclass(model,ScopedModel): valid=set(model.all_objects.filter(organization_id=org_id,pk__in=pk_set).values_list('pk',flat=True))
    elif model is Group: valid=set(OrganizationGroup.all_objects.filter(organization_id=org_id,group_id__in=pk_set).values_list('group_id',flat=True))
    elif model is get_user_model(): valid=set(Membership.all_objects.filter(organization_id=org_id,user_id__in=pk_set,active=True).values_list('user_id',flat=True))
    else: return
    if valid!=set(pk_set): raise ValidationError('다른 조직의 그룹 또는 사용자를 연결할 수 없습니다.')

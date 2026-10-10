from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from apps.core.services import audit
from apps.organizations.scoping import is_org_admin, organization_group_ids
from .models import Connection, FeatureBinding, ConfigurationRevision

def usable_connections(user):
    if is_org_admin(user): return Connection.objects.filter(active=True)
    return Connection.objects.filter(active=True).filter(Q(owner=user)|Q(shared=True,groups__isnull=True)|Q(shared=True,groups__pk__in=organization_group_ids(user))).distinct()

def resolve_binding(feature_code, user):
    binding=FeatureBinding.objects.select_related('connection','data_resource').filter(feature_code=feature_code).first()
    if binding and binding.connection and not binding.connection.can_use(user): raise PermissionDenied('연결 사용 권한이 없습니다.')
    return binding

@transaction.atomic
def save_binding(form, actor):
    obj=form.save(commit=False)
    if obj.connection and not can_manage(actor,obj.connection): raise PermissionDenied('연결 관리 권한이 없습니다.')
    if obj.pk:
        previous=FeatureBinding.objects.select_for_update().get(pk=obj.pk)
        if form.cleaned_data.get('revision_token') != previous.revision:
            raise ValidationError('다른 관리자가 변경했습니다. 새로 고침 후 다시 저장하세요.')
        if previous.connection and not can_manage(actor,previous.connection): raise PermissionDenied('기능 연결 관리 권한이 없습니다.')
        obj.revision=previous.revision+1
    else: obj.revision=1
    obj.full_clean();obj.save()
    ConfigurationRevision.objects.create(binding=obj,number=obj.revision,created_by=actor,snapshot={
        'feature_code':obj.feature_code,'connection_id':obj.connection_id,'data_resource_id':obj.data_resource_id,
        'resource_id':obj.resource_id,'config':obj.config,'field_mapping':obj.field_mapping})
    audit(actor,'binding.updated',obj,{'revision':obj.revision})
    return obj

def can_manage(user, connection):
    from apps.organizations.scoping import current_organization
    org = current_organization()
    return bool(org and connection.organization_id == org.pk and is_org_admin(user))

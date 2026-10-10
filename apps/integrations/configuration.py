from apps.organizations.scoping import is_org_admin
"""Portable, credential-free configuration; never export encrypted secrets or owners."""
import json
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from .models import Connection, DataResource, FeatureBinding
from .forms import FeatureBindingForm
from .services import can_manage, save_binding
from .validation import validate_options
from apps.core.services import audit


def export_configuration(actor):
    connections=Connection.objects.all() if is_org_admin(actor) else Connection.objects.filter(owner=actor)
    result={'version':1,'connections':[],'resources':[],'bindings':[]}
    for connection in connections:
        validate_options(connection.config)
        result['connections'].append({k:getattr(connection,k) for k in ['name','provider','active','config']})
    resources=DataResource.objects.filter(connection__in=connections).select_related('connection')
    for resource in resources:
        validate_options(resource.config);validate_options(resource.schema)
        result['resources'].append({'name':resource.name,'connection':resource.connection.name,'external_id':resource.external_id,'config':resource.config,'schema':resource.schema})
    for binding in FeatureBinding.objects.filter(connection__in=connections).select_related('connection','data_resource'):
        validate_options(binding.config);validate_options(binding.field_mapping)
        result['bindings'].append({'feature_code':binding.feature_code,'connection':binding.connection.name,'resource':binding.data_resource.name if binding.data_resource else None,'resource_id':binding.resource_id,'config':binding.config,'field_mapping':binding.field_mapping})
    return result


@transaction.atomic
def import_configuration(data, actor):
    if not isinstance(data,dict) or data.get('version') != 1 or len(json.dumps(data)) > 1024*1024:
        raise ValidationError('지원하지 않는 구성 파일이거나 크기가 1MB를 초과했습니다.')
    if set(data) - {'version','connections','resources','bindings'}:
        raise ValidationError('구성 파일에 지원하지 않는 필드가 있습니다.')
    for key in ['connections','resources','bindings']:
        if not isinstance(data.get(key,[]),list) or len(data.get(key,[])) > 1000: raise ValidationError('구성 목록이 올바르지 않습니다.')
    connections={}
    for values in data.get('connections',[]):
        if not isinstance(values,dict) or set(values)-{'name','provider','active','config'}: raise ValidationError('연결 구성에 허용되지 않은 필드가 있습니다. 비밀값은 가져올 수 없습니다.')
        obj=Connection.objects.select_for_update().filter(name=values.get('name')).first()
        if obj and not can_manage(actor,obj): raise PermissionDenied('다른 사용자의 연결은 덮어쓸 수 없습니다.')
        obj=obj or Connection(owner=actor)
        for field in ['name','provider','active','config']:
            if field in values: setattr(obj,field,values[field])
        obj.full_clean();obj.save();connections[obj.name]=obj
    resources={}
    for values in data.get('resources',[]):
        if not isinstance(values,dict) or set(values)-{'name','connection','external_id','config','schema'}: raise ValidationError('자원 구성이 올바르지 않습니다.')
        connection=connections.get(values.get('connection'))
        if connection is None: raise ValidationError('가져오는 연결에 속한 자원만 가져올 수 있습니다.')
        obj=DataResource.objects.select_for_update().filter(connection=connection,name=values.get('name')).first() or DataResource(connection=connection)
        for field in ['name','external_id','config','schema']:
            if field in values: setattr(obj,field,values[field])
        validate_options(obj.schema);obj.full_clean();obj.save();resources[(connection.name,obj.name)]=obj
    for values in data.get('bindings',[]):
        if not isinstance(values,dict) or set(values)-{'feature_code','connection','resource','resource_id','config','field_mapping'}: raise ValidationError('기능 구성이 올바르지 않습니다.')
        connection=connections.get(values.get('connection'))
        if connection is None: raise ValidationError('기능 연결 계정이 없습니다.')
        resource=resources.get((connection.name,values.get('resource')))
        if values.get('resource') and resource is None: raise ValidationError('기능에 연결할 자원이 없습니다.')
        previous=FeatureBinding.objects.select_for_update().filter(feature_code=values.get('feature_code')).first()
        payload={'feature_code':values.get('feature_code'),'connection':connection.pk,'data_resource':resource.pk if resource else '', 'resource_id':values.get('resource_id',''),'config':json.dumps(values.get('config',{})),'field_mapping':json.dumps(values.get('field_mapping',{})),'revision_token':previous.revision if previous else 0}
        form=FeatureBindingForm(payload,instance=previous)
        if not form.is_valid(): raise ValidationError(str(form.errors))
        save_binding(form,actor)
    audit(actor,'configuration.imported',details={'connections':len(connections),'resources':len(resources),'bindings':len(data.get('bindings',[]))})

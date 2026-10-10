from apps.organizations.scoping import is_org_admin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from apps.core.services import audit
from .models import Connection, DataResource, FeatureBinding
from .forms import ConnectionForm, DataResourceForm, FeatureBindingForm
from .services import save_binding, can_manage
staff=user_passes_test(is_org_admin)
@login_required
@staff
def index(request):
    managed=Connection.objects.all() if is_org_admin(request.user) else Connection.objects.filter(owner=request.user)
    return render(request,'integrations/list.html',{'connections':managed,'resources':DataResource.objects.filter(connection__in=managed).select_related('connection'),'bindings':FeatureBinding.objects.filter(connection__in=managed).select_related('connection')})
@login_required
@staff
def edit(request, kind, pk=None):
    classes={'connection':(Connection,ConnectionForm),'resource':(DataResource,DataResourceForm),'binding':(FeatureBinding,FeatureBindingForm)}
    if kind not in classes:
        from django.http import Http404
        raise Http404
    model, form_class=classes[kind]
    obj=get_object_or_404(model,pk=pk) if pk else None
    connection = obj if kind=='connection' else obj.connection if obj else None
    if connection and not can_manage(request.user,connection):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('연결 관리 권한이 없습니다.')
    form=form_class(request.POST or None,instance=obj)
    managed=Connection.objects.all() if is_org_admin(request.user) else Connection.objects.filter(owner=request.user)
    if 'connection' in form.fields: form.fields['connection'].queryset=managed
    if 'data_resource' in form.fields: form.fields['data_resource'].queryset=DataResource.objects.filter(connection__in=managed)
    if request.method=='POST' and form.is_valid():
        try:
            if kind=='binding': obj=save_binding(form,request.user)
            else:
                obj=form.save(commit=False)
                if kind=='connection':
                    if not obj.pk: obj.owner=request.user
                    secret=form.cleaned_data.get('secrets_input')
                    if secret is not None: obj.set_secrets(secret)
                    obj.status='UNTESTED'
                obj.full_clean();obj.save();form.save_m2m();audit(request.user,kind+'.updated',obj)
            messages.success(request,'설정을 저장했습니다.');return redirect('integration_list')
        except ValidationError as exc: form.add_error(None,exc)
    return render(request,'integrations/form.html',{'form':form,'kind':kind,'object':obj})
@login_required
@staff
@require_POST
def validate_connection(request, pk):
    obj=get_object_or_404(Connection,pk=pk)
    if not can_manage(request.user,obj):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('연결 관리 권한이 없습니다.')
    try:
        obj.full_clean();obj.secrets()
        obj.status='CONFIG_VALID';obj.save(update_fields=['status'])
        audit(request.user,'connection.configuration_validated',obj)
        messages.success(request,'설정과 비밀값 복호화를 확인했습니다. 외부 서비스 접속 여부는 확인하지 않았습니다.')
    except ValidationError:
        messages.error(request,'설정 검증에 실패했습니다. 옵션과 서버 암호화 키를 확인하세요.')
    return redirect('integration_list')

@login_required
@staff
@require_POST
def delete(request, kind, pk):
    from django.db.models.deletion import ProtectedError
    classes={'connection':Connection,'resource':DataResource,'binding':FeatureBinding}
    if kind not in classes:
        from django.http import Http404
        raise Http404
    obj=get_object_or_404(classes[kind],pk=pk)
    connection=obj if kind=='connection' else obj.connection
    if connection and not can_manage(request.user,connection):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('연결 관리 권한이 없습니다.')
    try:
        from django.db import transaction
        with transaction.atomic():
            audit(request.user,kind+'.deleted',obj)
            obj.delete()
        messages.success(request,'설정을 삭제했습니다.')
    except ProtectedError:
        messages.error(request,'이 설정을 사용하는 자원이나 기능 연결을 먼저 삭제하거나 변경하세요.')
    return redirect('integration_list')

@login_required
@staff
def configuration_transfer(request):
    import json
    from django import forms
    from .configuration import import_configuration
    class ImportForm(forms.Form):
        configuration = forms.JSONField(label='구성 JSON',widget=forms.Textarea(attrs={'rows':14}),help_text='비밀값은 제외됩니다. 연결명과 기능 코드가 같으면 기존 설정을 갱신합니다.')
    form=ImportForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:
            import_configuration(form.cleaned_data['configuration'],request.user)
            messages.success(request,'구성을 가져왔습니다. 비밀 정보는 연결별로 다시 입력하세요.')
            return redirect('integration_list')
        except (ValidationError,ValueError,TypeError,KeyError) as exc:
            form.add_error(None,exc.messages if isinstance(exc,ValidationError) else '구성 형식을 확인하세요.')
    return render(request,'integrations/transfer.html',{'form':form})

@login_required
@staff
def configuration_export(request):
    from django.http import JsonResponse
    from .configuration import export_configuration
    response=JsonResponse(export_configuration(request.user),json_dumps_params={'ensure_ascii':False,'indent':2})
    response['Content-Disposition']='attachment; filename="manualbook-configuration.json"'
    response['Cache-Control']='no-store'
    return response

@login_required
@staff
@require_POST
def restore_revision(request, pk, number):
    from django.db import transaction
    from django.core.exceptions import PermissionDenied
    from .models import ConfigurationRevision
    from .services import can_manage
    try:
        with transaction.atomic():
            binding=get_object_or_404(FeatureBinding.objects.select_for_update(),pk=pk)
            revision=get_object_or_404(ConfigurationRevision,binding=binding,number=number)
            if binding.connection and not can_manage(request.user,binding.connection): raise PermissionDenied('기능 연결 관리 권한이 없습니다.')
            snapshot=revision.snapshot
            form=FeatureBindingForm({'feature_code':binding.feature_code,'connection':snapshot.get('connection_id') or '', 'data_resource':snapshot.get('data_resource_id') or '', 'resource_id':snapshot.get('resource_id',''),'config':__import__('json').dumps(snapshot.get('config',{})),'field_mapping':__import__('json').dumps(snapshot.get('field_mapping',{})), 'revision_token':request.POST.get('revision_token')},instance=binding)
            if not form.is_valid(): raise ValidationError(str(form.errors))
            restored=save_binding(form,request.user)
            audit(request.user,'binding.revision_restored',restored,{'from_revision':number,'new_revision':restored.revision})
        messages.success(request,'이전 설정을 새 버전으로 복원했습니다.')
    except ValidationError as exc:
        messages.error(request,' '.join(exc.messages))
    return redirect('integration_edit',kind='binding',pk=pk)

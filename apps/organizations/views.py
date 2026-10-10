from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,IntegrityError
from django.db.models.deletion import ProtectedError
from django.contrib import messages
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_POST
from apps.core.services import audit
from .models import Organization,Membership,Department,OrganizationGroup
from .forms import OrganizationForm,MembershipForm,DepartmentForm,OrganizationGroupForm
from .scoping import organization_scope,current_organization
from .decorators import require_org_admin
from .backends import organization_username

def global_admin(view):
    @wraps(view)
    def wrapped(request,*args,**kwargs):
        if not request.user.is_active or not request.user.is_superuser: raise PermissionDenied('전체 관리자 권한이 필요합니다.')
        return view(request,*args,**kwargs)
    return wrapped

@login_required
def organization_list(request):
    orgs=Organization.objects.all() if request.user.is_superuser else Organization.objects.filter(active=True,pk__in=Membership.all_objects.filter(user=request.user,active=True).values('organization_id'))
    return render(request,'organizations/list.html',{'organizations':orgs})

@login_required
@global_admin
def organization_edit(request,pk=None):
    obj=get_object_or_404(Organization,pk=pk) if pk else None
    form=OrganizationForm(request.POST or None,instance=obj)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                org=form.save()
                with organization_scope(org):
                    if obj is None:
                        data=form.cleaned_data
                        user=get_user_model().objects.create_user(username=organization_username(org,data['admin_username']),email=data.get('admin_email',''),password=data['admin_password'])
                        Membership.objects.create(user=user,role='admin',active=True)
                        from apps.core.bootstrap import seed_platform
                        seed_platform()
                    audit(request.user,'organization.updated' if obj else 'organization.created',org)
            messages.success(request,'조직을 저장했습니다.'); return redirect('organization_list')
        except (ValidationError,IntegrityError) as exc: form.add_error(None,exc.messages if isinstance(exc,ValidationError) else '중복된 조직 또는 아이디입니다.')
    return render(request,'organizations/form.html',{'form':form,'title':'조직 수정' if obj else '조직 추가'})

@login_required
@require_org_admin
def members(request):
    return render(request,'organizations/members.html',{'members':Membership.objects.select_related('user','department').prefetch_related('groups')})

@login_required
@require_org_admin
def member_edit(request,pk=None):
    obj=get_object_or_404(Membership,pk=pk) if pk else None
    form=MembershipForm(request.POST or None,instance=obj)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                org=Organization.objects.select_for_update().get(pk=current_organization().pk)
                saved=form.save(commit=False)
                if obj:
                    previous=Membership.objects.get(pk=obj.pk)
                    if previous.role=='admin' and previous.active and not (saved.role=='admin' and saved.active) and Membership.objects.filter(role='admin',active=True).count()<=1:
                        raise ValidationError('마지막 활성 조직 관리자는 해제할 수 없습니다.')
                else:
                    data=form.cleaned_data
                    saved.user=get_user_model().objects.create_user(username=organization_username(org,data['username']),email=data.get('email',''),first_name=data.get('first_name',''),password=data['password'])
                audit(request.user,'membership.updated' if obj else 'membership.created',saved)
                saved.save(); form.save_m2m()
            messages.success(request,'구성원 정보를 저장했습니다.'); return redirect('organization_members')
        except (ValidationError,IntegrityError) as exc: form.add_error(None,exc.messages if isinstance(exc,ValidationError) else '이미 등록된 아이디입니다.')
    return render(request,'organizations/form.html',{'form':form,'title':'구성원 수정' if obj else '구성원 추가'})

@login_required
@require_org_admin
def directory(request,kind):
    model=Department if kind=='departments' else OrganizationGroup if kind=='groups' else None
    if model is None:
        from django.http import Http404
        raise Http404
    return render(request,'organizations/directory.html',{'items':model.objects.all(),'kind':kind,'title':'부서 관리' if kind=='departments' else '그룹 관리'})

@login_required
@require_org_admin
def directory_edit(request,kind,pk=None):
    model,form_type=(Department,DepartmentForm) if kind=='departments' else (OrganizationGroup,OrganizationGroupForm) if kind=='groups' else (None,None)
    if model is None:
        from django.http import Http404
        raise Http404
    obj=get_object_or_404(model,pk=pk) if pk else None
    form=form_type(request.POST or None,instance=obj)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            saved=form.save(); audit(request.user,kind+'.updated',saved)
        messages.success(request,'저장했습니다.'); return redirect('organization_directory',kind=kind)
    return render(request,'organizations/form.html',{'form':form,'title':'부서 설정' if kind=='departments' else '그룹 설정'})

@login_required
@require_org_admin
@require_POST
def directory_delete(request,kind,pk):
    model=Department if kind=='departments' else OrganizationGroup if kind=='groups' else None
    if model is None:
        from django.http import Http404
        raise Http404
    obj=get_object_or_404(model,pk=pk)
    try:
        with transaction.atomic():
            audit(request.user,kind+'.deleted',obj)
            group=obj.group if kind=='groups' else None
            obj.delete()
            if group: group.delete()
        messages.success(request,'삭제했습니다.')
    except ProtectedError: messages.error(request,'참조 중인 하위 부서 또는 객체를 먼저 정리하세요.')
    return redirect('organization_directory',kind=kind)

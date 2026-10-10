from contextvars import ContextVar
from contextlib import contextmanager
from django.db import models
from django.core.exceptions import ValidationError, ObjectDoesNotExist, FieldDoesNotExist, PermissionDenied
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

_current=ContextVar('manualbook_organization',default=None)
def current_organization(): return _current.get()

@contextmanager
def organization_scope(organization):
    token=_current.set(organization)
    try: yield organization
    finally: _current.reset(token)

organization_context=organization_scope

def is_org_admin(user,organization=None):
    organization=organization or current_organization()
    if not organization or not getattr(user,'is_authenticated',False) or not user.is_active or not organization.active: return False
    if user.is_superuser: return True
    from .models import Membership
    return Membership.all_objects.filter(organization=organization,user=user,active=True,role='admin').exists()

def organization_group_ids(user,organization=None):
    organization=organization or current_organization()
    if not organization or not getattr(user,'is_authenticated',False) or not user.is_active: return set()
    from .models import Membership
    member=Membership.all_objects.filter(organization=organization,user=user,active=True).first()
    return set(member.groups.values_list('group_id',flat=True)) if member else set()

class ScopedQuerySet(models.QuerySet):
    def _clone(self):
        result=super()._clone()
        result._bound_scope=getattr(self,'_bound_scope',False)
        result._scope_id=getattr(self,'_scope_id',None)
        return result
    def _guard(self):
        if not getattr(self,'_bound_scope',False): return
        org=current_organization()
        if getattr(self,'_scope_id',None)!=(org.pk if org else None):
            raise PermissionDenied('이 조회의 조직 컨텍스트가 변경되었습니다.')
    def _fetch_all(self):
        self._guard()
        return super()._fetch_all()
    def get(self,*args,**kwargs):
        self._guard()
        return super().get(*args,**kwargs)
    def count(self):
        self._guard()
        return super().count()
    def exists(self):
        self._guard()
        return super().exists()
    def aggregate(self,*args,**kwargs):
        self._guard()
        return super().aggregate(*args,**kwargs)
    def iterator(self,*args,**kwargs):
        self._guard()
        return super().iterator(*args,**kwargs)
    async def aiterator(self,*args,**kwargs):
        self._guard()
        async for obj in super().aiterator(*args,**kwargs): yield obj
    def delete(self):
        self._guard()
        return super().delete()
    def create(self,**kwargs):
        self._guard()
        return super().create(**kwargs)
    def update(self,**kwargs):
        self._guard()
        if 'organization' in kwargs or 'organization_id' in kwargs: raise ValidationError('조직 소유권을 일괄 변경할 수 없습니다.')
        for name in kwargs:
            try: field=self.model._meta.get_field(name)
            except FieldDoesNotExist: field=self.model._meta.get_field(name.removesuffix('_id'))
            if field.is_relation: raise ValidationError('관련 객체 변경은 save()를 사용하세요.')
        return super().update(**kwargs)
    def bulk_create(self,objs,**kwargs):
        self._guard()
        for obj in objs: obj._validate_scope(); obj.full_clean()
        return super().bulk_create(objs,**kwargs)
    def bulk_update(self,objs,fields,**kwargs):
        self._guard()
        if any(self.model._meta.get_field(name).is_relation for name in fields): raise ValidationError('관련 객체 변경은 save()를 사용하세요.')
        for obj in objs: obj._validate_scope()
        return super().bulk_update(objs,fields,**kwargs)

class ScopedManager(models.Manager.from_queryset(ScopedQuerySet)):
    def get_queryset(self):
        queryset=super().get_queryset(); org=current_organization()
        queryset=queryset.filter(organization_id=org.pk) if org else queryset.none()
        queryset._bound_scope=True; queryset._scope_id=org.pk if org else None
        return queryset

class ScopedModel(models.Model):
    organization=models.ForeignKey('organizations.Organization',on_delete=models.PROTECT)
    objects=ScopedManager()
    all_objects=models.Manager()
    class Meta:
        abstract=True
    def _validate_scope(self):
        org=current_organization()
        if not org: raise ValidationError('조직 컨텍스트가 필요합니다.')
        if not self.organization_id: self.organization=org
        if self.organization_id != org.pk: raise ValidationError('다른 조직의 객체를 저장할 수 없습니다.')
        if self.pk:
            persisted=type(self).all_objects.filter(pk=self.pk).values_list('organization_id',flat=True).first()
            if persisted and persisted != self.organization_id: raise ValidationError('조직 소유권을 변경할 수 없습니다.')
    def clean(self):
        super().clean(); self._validate_scope()
        from .models import Membership,OrganizationGroup
        for field in self._meta.fields:
            if not field.is_relation or field.name=='organization' or not getattr(self,field.attname,None): continue
            try: related=getattr(self,field.name)
            except ObjectDoesNotExist: raise ValidationError({field.name:'관련 객체를 찾을 수 없습니다.'})
            if isinstance(related,ScopedModel) and related.organization_id != self.organization_id: raise ValidationError({field.name:'같은 조직의 객체를 선택하세요.'})
            if isinstance(related,Group):
                existing=OrganizationGroup.all_objects.filter(group=related)
                if self._meta.label_lower=='organizations.organizationgroup':
                    if existing.exclude(pk=self.pk).exists(): raise ValidationError({field.name:'다른 조직에서 사용하는 그룹입니다.'})
                elif not existing.filter(organization_id=self.organization_id).exists(): raise ValidationError({field.name:'같은 조직의 그룹을 선택하세요.'})
            if isinstance(related,get_user_model()) and self._meta.label_lower!='organizations.membership':
                if not related.is_superuser:
                    unchanged=bool(self.pk and type(self).all_objects.filter(pk=self.pk,**{field.attname:related.pk}).exists())
                    membership=Membership.all_objects.filter(organization_id=self.organization_id,user=related)
                    if not unchanged: membership=membership.filter(active=True,user__is_active=True)
                    if not membership.exists(): raise ValidationError({field.name:'같은 조직의 사용자를 선택하세요.'})
    def save(self,*args,**kwargs):
        self._validate_scope(); self.full_clean()
        return super().save(*args,**kwargs)

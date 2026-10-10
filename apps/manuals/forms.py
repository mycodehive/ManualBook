from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from apps.organizations.models import OrganizationGroup, Membership
from apps.organizations.scoping import current_organization
from .models import ManualSpace, ManualNode, ManualPermissionAssignment

class ManualScopedForm(forms.ModelForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        org=current_organization()
        if not org or (self.instance.organization_id and self.instance.organization_id != org.pk):
            raise PermissionDenied('조직 범위가 올바르지 않습니다.')
        self.instance.organization=org
        self.organization=org

class SpaceForm(ManualScopedForm):
    class Meta:
        model=ManualSpace
        fields=['name','description','view_groups','edit_groups','approve_groups','active','require_approval','allow_self_approval']
        widgets={name:forms.CheckboxSelectMultiple() for name in ['view_groups','edit_groups','approve_groups']}
        labels={'name':'공간 이름','description':'설명','view_groups':'열람 그룹','edit_groups':'편집 그룹','approve_groups':'관리·승인 그룹','active':'활성','require_approval':'승인 후 게시','allow_self_approval':'본인 문서 승인 허용'}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        ids=OrganizationGroup.objects.filter(organization=self.organization).values_list('group_id',flat=True)
        for name in ['view_groups','edit_groups','approve_groups']:
            self.fields[name].queryset=Group.objects.filter(pk__in=ids)

class NodeForm(ManualScopedForm):
    class Meta:
        model=ManualNode
        fields=['title','kind','parent','sort_order','archived']
        labels={'title':'제목','kind':'유형','parent':'상위 폴더','sort_order':'표시 순서','archived':'보관 처리'}
    def __init__(self,*args,space,**kwargs):
        super().__init__(*args,**kwargs)
        if space.organization_id != self.organization.pk: raise PermissionDenied('다른 조직의 공간입니다.')
        self.instance.space=space
        self.fields['parent'].queryset=space.nodes.filter(kind='folder',deleted=False).exclude(pk=self.instance.pk)

class PermissionForm(ManualScopedForm):
    class Meta:
        model=ManualPermissionAssignment
        fields=['group','user','action','effect']
        labels={'group':'그룹','user':'사용자','action':'작업','effect':'규칙'}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        ids=OrganizationGroup.objects.filter(organization=self.organization).values_list('group_id',flat=True)
        self.fields['group'].queryset=Group.objects.filter(pk__in=ids)
        members=Membership.objects.filter(organization=self.organization,active=True).values_list('user_id',flat=True)
        self.fields['user'].queryset=get_user_model().objects.filter(pk__in=members,is_active=True)
    def clean(self):
        data=super().clean()
        if bool(data.get('group'))==bool(data.get('user')): raise forms.ValidationError('그룹 또는 사용자 중 하나만 선택하세요.')
        return data

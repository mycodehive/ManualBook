from django import forms
from .models import ManualSpace, ManualNode
class SpaceForm(forms.ModelForm):
    class Meta:
        model=ManualSpace
        fields=['name','description','view_groups','edit_groups','approve_groups','active','require_approval','allow_self_approval']
        widgets={name:forms.CheckboxSelectMultiple() for name in ['view_groups','edit_groups','approve_groups']}
        labels={'name':'공간 이름','description':'설명','view_groups':'열람 그룹','edit_groups':'편집 그룹','approve_groups':'관리·승인 그룹','active':'활성','require_approval':'승인 후 게시','allow_self_approval':'본인 문서 승인 허용'}
class NodeForm(forms.ModelForm):
    class Meta:
        model=ManualNode
        fields=['title','kind','parent','sort_order','archived']
        labels={'title':'제목','kind':'유형','parent':'상위 폴더','sort_order':'표시 순서','archived':'보관 처리'}
    def __init__(self,*args,space,**kwargs):
        super().__init__(*args,**kwargs)
        self.instance.space=space
        self.fields['parent'].queryset=space.nodes.filter(kind='folder',deleted=False).exclude(pk=self.instance.pk)

from .models import ManualPermissionAssignment
class PermissionForm(forms.ModelForm):
    class Meta:
        model=ManualPermissionAssignment
        fields=['group','user','action','effect']
        labels={'group':'그룹','user':'사용자','action':'작업','effect':'규칙'}
    def clean(self):
        data=super().clean()
        if bool(data.get('group'))==bool(data.get('user')): raise forms.ValidationError('그룹 또는 사용자 중 하나만 선택하세요.')
        return data

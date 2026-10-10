from django import forms
from django.contrib.auth import get_user_model,password_validation
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError, PermissionDenied
from .models import Organization,Membership,Department,OrganizationGroup
from .scoping import ScopedModel,current_organization

class ScopedModelForm(forms.ModelForm):
    def __init__(self,*args,organization=None,user=None,**kwargs):
        super().__init__(*args,**kwargs)
        org=organization or current_organization()
        if not org or (self.instance.organization_id and self.instance.organization_id != org.pk): raise PermissionDenied('조직 범위가 올바르지 않습니다.')
        self.fields.pop('organization',None)
        self.instance.organization=org
        for field in self.fields.values():
            if not hasattr(field,'queryset'): continue
            model=field.queryset.model
            if issubclass(model,ScopedModel): field.queryset=model.all_objects.filter(organization=org)
            elif model is Group: field.queryset=Group.objects.filter(pk__in=OrganizationGroup.all_objects.filter(organization=org).values('group_id'))
            elif model is get_user_model(): field.queryset=model.objects.filter(pk__in=Membership.all_objects.filter(organization=org,active=True,user__is_active=True).values('user_id'))

class OrganizationForm(forms.ModelForm):
    admin_username=forms.CharField(label='첫 관리자 아이디',max_length=100,required=False)
    admin_email=forms.EmailField(label='첫 관리자 이메일',required=False)
    admin_password=forms.CharField(label='새 관리자 비밀번호',required=False,widget=forms.PasswordInput)
    confirmation=forms.CharField(label='비밀번호 확인',required=False,widget=forms.PasswordInput)
    class Meta:
        model=Organization
        fields=['name','slug','active']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance.pk:
            self.fields['slug'].disabled=True
            for name in ['admin_username','admin_email','admin_password','confirmation']: self.fields.pop(name)
        else: self.fields['admin_username'].required=True
    def clean(self):
        data=super().clean()
        if self.instance.pk: return data
        password=data.get('admin_password')
        if not password: raise ValidationError('새 관리자의 비밀번호를 입력하세요.')
        if password!=data.get('confirmation'): raise ValidationError('비밀번호가 일치하지 않습니다.')
        import re
        if not re.fullmatch(r'[A-Za-z0-9_.@+-]{1,100}',data.get('admin_username','')): raise ValidationError('관리자 아이디 형식이 올바르지 않습니다.')
        password_validation.validate_password(password,get_user_model()(username=data.get('admin_username'),email=data.get('admin_email','')))
        return data

class MembershipForm(ScopedModelForm):
    username=forms.CharField(label='아이디',max_length=100)
    email=forms.EmailField(label='새 사용자 이메일',required=False)
    first_name=forms.CharField(label='새 사용자 이름',max_length=150,required=False)
    password=forms.CharField(label='새 사용자 비밀번호',required=False,widget=forms.PasswordInput)
    password_confirm=forms.CharField(label='비밀번호 확인',required=False,widget=forms.PasswordInput)
    class Meta:
        model=Membership
        fields=['role','active','department','groups']
        widgets={'groups':forms.CheckboxSelectMultiple}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance.pk:
            self.fields['username'].initial=self.instance.display_username; self.fields['username'].disabled=True
            for name in ['email','first_name','password','password_confirm']: self.fields.pop(name)
    def clean(self):
        data=super().clean()
        if self.instance.pk: return data
        from .backends import organization_username
        username=organization_username(self.instance.organization,data.get('username'))
        if get_user_model().objects.filter(username=username).exists(): raise ValidationError('이 조직에서 이미 사용하는 아이디입니다. 기존 구성원 화면에서 관리하세요.')
        password=data.get('password')
        if not password: raise ValidationError('새 사용자 비밀번호를 입력하세요.')
        if password!=data.get('password_confirm'): raise ValidationError('비밀번호가 일치하지 않습니다.')
        password_validation.validate_password(password,get_user_model()(username=username,email=data.get('email','')))
        return data

class DepartmentForm(ScopedModelForm):
    class Meta:
        model=Department
        fields=['name','parent','description','active']

class OrganizationGroupForm(ScopedModelForm):
    class Meta:
        model=OrganizationGroup
        fields=['name']

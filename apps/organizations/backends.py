import re
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Membership
from .scoping import current_organization

def organization_username(organization,local_name):
    if not re.fullmatch(r'[A-Za-z0-9_.@+-]{1,100}',local_name or ''): raise ValidationError('아이디는 영문·숫자·_.@+- 문자 1~100자로 입력하세요.')
    return 'org'+str(organization.pk)+'__'+local_name

class OrganizationBackend(ModelBackend):
    def authenticate(self,request,username=None,password=None,**kwargs):
        if username is None: username=kwargs.get(get_user_model().USERNAME_FIELD)
        if username is None or password is None: return None
        org=getattr(request,'organization',None) or current_organization()
        if not org:
            user=super().authenticate(request,username=username,password=password,**kwargs)
            return user if user and user.is_superuser else None
        if not org.active: return None
        try: canonical=organization_username(org,username)
        except ValidationError: canonical=username
        user=super().authenticate(request,username=canonical,password=password,**kwargs)
        if not user and canonical!=username:
            user=super().authenticate(request,username=username,password=password,**kwargs)
        if user and not user.is_superuser and Membership.all_objects.filter(organization=org,user=user,active=True).exists(): return user
        return None

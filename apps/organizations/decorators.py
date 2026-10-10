from functools import wraps
from django.core.exceptions import PermissionDenied
from .scoping import is_org_admin
def require_org_admin(view):
    @wraps(view)
    def wrapped(request,*args,**kwargs):
        if not is_org_admin(request.user): raise PermissionDenied('조직 관리자 권한이 필요합니다.')
        return view(request,*args,**kwargs)
    return wrapped

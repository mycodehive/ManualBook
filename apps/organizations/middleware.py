import re
from contextlib import contextmanager
from django.http import HttpResponseRedirect,Http404
from django.core.exceptions import PermissionDenied
from django.urls import get_script_prefix,set_script_prefix
from django.contrib.auth.views import redirect_to_login
from django.utils.cache import patch_vary_headers
from .models import Organization,Membership
from .scoping import organization_scope

class OrganizationMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        request.organization=None; request.membership=None; request.public_read_allowed=False
        match=re.match(r'^/o/([a-zA-Z0-9_-]+)(/.*)?$',request.path_info)
        if not match:
            allowed=request.path_info in ('/', '/intro', '/intro/', '/robots.txt', '/sitemap.xml') or request.path_info.startswith(('/organizations/','/admin/','/static/','/login/','/logout/','/health/'))
            if not allowed:
                return HttpResponseRedirect('/organizations/' if request.user.is_authenticated else '/login/?next=/organizations/')
            with organization_scope(None): response=self.get_response(request)
            if request.user.is_authenticated or request.path_info in ('/login/', '/logout/'):
                response['Cache-Control']='private, no-store'
                patch_vary_headers(response,('Cookie',))
            return response
        org=Organization.objects.filter(slug=match.group(1),active=True).first()
        if not org: raise Http404('조직을 찾을 수 없습니다.')
        inner=match.group(2) or '/'
        from .public_access import is_public_read
        public=inner in ('/login/','/logout/') or is_public_read(request,org,inner)
        if not request.user.is_authenticated and not public:
            return redirect_to_login(request.get_full_path(),'/o/'+org.slug+'/login/')
        member=Membership.all_objects.filter(organization=org,user=request.user,active=True).first() if request.user.is_authenticated else None
        if request.user.is_authenticated and not public and (not request.user.is_active or (not request.user.is_superuser and not member)):
            raise PermissionDenied('이 조직에 가입되어 있지 않습니다.')
        if match.group(2) is None: return HttpResponseRedirect(request.path+'/')
        request.organization=org; request.membership=member
        request.path_info=inner
        tenant_script=request.META.get('SCRIPT_NAME','').rstrip('/')+'/o/'+org.slug
        @contextmanager
        def request_scope():
            old_prefix=get_script_prefix(); old_meta=request.META.get('SCRIPT_NAME','')
            request.META['SCRIPT_NAME']=tenant_script
            set_script_prefix(tenant_script+'/')
            try:
                with organization_scope(org): yield
            finally:
                request.META['SCRIPT_NAME']=old_meta; set_script_prefix(old_prefix)
        with request_scope(): response=self.get_response(request)
        if response.streaming:
            stream=response.streaming_content
            if response.is_async:
                async def async_stream():
                    with request_scope():
                        async for chunk in stream: yield chunk
                response.streaming_content=async_stream()
            else:
                def scoped_stream():
                    with request_scope(): yield from stream
                response.streaming_content=scoped_stream()
        response['Cache-Control']='private, no-store'
        patch_vary_headers(response,('Cookie',))
        return response

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect
from apps.organizations.scoping import is_org_admin
from .forms import ProfileForm
@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save(); messages.success(request, '프로필을 저장했습니다.'); return redirect('account_profile')
    return render(request, 'accounts/profile.html', {'form': form})
@login_required
@user_passes_test(is_org_admin)
def management(request):
    return redirect('organization_members')

from django.contrib.auth.views import LoginView
from django.urls import reverse
class OrganizationLoginView(LoginView):
    template_name='registration/login.html'
    def post(self,request,*args,**kwargs):
        from apps.organizations.throttling import retry_after
        wait=retry_after(request)
        if wait:
            from django.http import HttpResponse
            response=HttpResponse('로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요.',status=429)
            response['Retry-After']=str(wait)
            return response
        return super().post(request,*args,**kwargs)
    def form_invalid(self,form):
        from apps.organizations.throttling import failure
        failure(self.request)
        return super().form_invalid(form)
    def form_valid(self,form):
        from apps.organizations.throttling import success
        success(self.request)
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'public_layout': True}
    def get_success_url(self):
        if self.request.user.is_superuser:
            return '/organizations/'
        target = self.get_redirect_url()
        if target and permitted_login_target(self.request, target):
            return target
        return login_destination(self.request)


def csrf_failure(request, reason=''):
    """Offer an explicit logout retry without executing a rejected mutation."""
    from django.views.csrf import csrf_failure as default_failure
    from django.utils.cache import patch_cache_control
    match = request.resolver_match
    if not match or match.url_name != 'logout':
        return default_failure(request, reason=reason)
    response = render(request, 'registration/logout_csrf_failure.html',
        {'logout_action': request.path}, status=403)
    patch_cache_control(response, private=True, no_cache=True, no_store=True, must_revalidate=True)
    return response


def login_destination(request):
    """Use an active membership; multiple organizations require an explicit choice."""
    if request.user.is_superuser:
        return '/organizations/'
    organization = getattr(request, 'organization', None)
    if organization:
        return reverse('home')
    from apps.organizations.models import Membership
    organizations = list(Membership.all_objects.filter(user=request.user, active=True,
        organization__active=True).select_related('organization').order_by('organization_id')[:2])
    return organizations[0].organization.get_absolute_url() if len(organizations) == 1 else reverse('organization_list')

def entry(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return redirect(login_destination(request))

@login_required
def identity_policy(request):
    from django.core.exceptions import PermissionDenied
    from django.db import transaction
    from django.contrib.admin.models import LogEntry, CHANGE
    from .models import IdentityPolicy
    from .forms import IdentityPolicyForm
    if not request.user.is_active or not request.user.is_superuser or getattr(request, 'organization', None):
        raise PermissionDenied('사이트 최고관리자만 사용자 아이디 정책을 설정할 수 있습니다.')
    policy, _ = IdentityPolicy.objects.get_or_create(pk=1)
    form = IdentityPolicyForm(request.POST or None, instance=policy)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            policy = form.save()
            LogEntry.objects.log_actions(user_id=request.user.pk, queryset=[policy], action_flag=CHANGE,
                change_message='사용자 생성 금지 아이디 정책 수정')
        messages.success(request, '사용자 아이디 정책을 저장했습니다.')
        return redirect('identity_policy')
    return render(request, 'accounts/identity_policy.html', {'form': form})


def permitted_login_target(request, target):
    from urllib.parse import urlsplit
    path = urlsplit(target).path
    org = getattr(request, 'organization', None)
    if org:
        return path.startswith('/o/' + org.slug + '/')
    if request.user.is_superuser:
        return True
    if path == '/organizations/':
        return True
    from apps.organizations.models import Membership
    return any(path.startswith('/o/' + slug + '/') for slug in Membership.all_objects.filter(
        user=request.user, active=True, organization__active=True).values_list('organization__slug', flat=True))

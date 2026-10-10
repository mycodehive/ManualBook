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
    def get_success_url(self):
        return self.get_redirect_url() or reverse('home' if getattr(self.request,'organization',None) else 'organization_list')

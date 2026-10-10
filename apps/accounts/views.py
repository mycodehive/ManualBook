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
    def get_success_url(self):
        return self.get_redirect_url() or reverse('home' if getattr(self.request,'organization',None) else 'organization_list')

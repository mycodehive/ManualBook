from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect
from .forms import ProfileForm
@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save(); messages.success(request, '프로필을 저장했습니다.'); return redirect('account_profile')
    return render(request, 'accounts/profile.html', {'form': form})
@login_required
@user_passes_test(lambda u: u.is_staff)
def management(request):
    return render(request, 'accounts/management.html')

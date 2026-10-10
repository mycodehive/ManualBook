from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect
from .models import SiteConfiguration, AuditEvent
from .forms import SiteConfigurationForm
from .services import audit

@login_required
def home(request):
    return render(request, 'core/home.html')

@login_required
@user_passes_test(lambda u: u.is_staff)
def settings_view(request):
    obj, _ = SiteConfiguration.objects.get_or_create(pk=1)
    form = SiteConfigurationForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save(); audit(request.user, 'settings.updated', obj)
        messages.success(request, '환경설정을 저장했습니다.'); return redirect('site_settings')
    return render(request, 'core/settings.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_staff)
def audit_log(request):
    from django.core.paginator import Paginator
    return render(request, 'core/audit.html', {'page_obj': Paginator(AuditEvent.objects.select_related('actor'), 50).get_page(request.GET.get('page'))})

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import Http404
from django.views.decorators.http import require_safe
from apps.organizations.scoping import is_org_admin
from .models import SiteConfiguration, AuditEvent
from .forms import SiteConfigurationForm
from .services import audit

@login_required
def home(request):
    return render(request, 'core/home.html')

@login_required
@user_passes_test(is_org_admin)
def settings_view(request):
    obj, _ = SiteConfiguration.objects.get_or_create()
    form = SiteConfigurationForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save(); audit(request.user, 'settings.updated', obj)
        messages.success(request, '환경설정을 저장했습니다.'); return redirect('site_settings')
    return render(request, 'core/settings.html', {'form': form})

@login_required
@user_passes_test(is_org_admin)
def audit_log(request):
    from django.core.paginator import Paginator
    return render(request, 'core/audit.html', {'page_obj': Paginator(AuditEvent.objects.select_related('actor'), 50).get_page(request.GET.get('page'))})


@require_safe
def intro(request):
    """A global introduction page; tenant workspaces keep their existing routes."""
    if getattr(request, 'organization', None) is not None:
        raise Http404
    return render(request, 'core/intro.html', {'public_layout': True})

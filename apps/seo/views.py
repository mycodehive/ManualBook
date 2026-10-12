from functools import wraps
from django.contrib import messages
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_safe, require_http_methods
from .forms import SEOConfigurationForm
from .models import SEOConfiguration
from .services import get_configuration, robots_text, sitemap_xml


def highest_admin(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if getattr(request, 'organization', None) is not None:
            raise Http404
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), '/login/')
        if not request.user.is_active or not request.user.is_superuser:
            raise PermissionDenied('사이트 최고 관리자만 SEO 설정을 관리할 수 있습니다.')
        return view(request, *args, **kwargs)
    return wrapped


@highest_admin
@require_safe
def detail(request):
    obj = SEOConfiguration.objects.filter(pk=1).first()
    return render(request, 'seo/detail.html', {'object': obj, 'seo': obj})


@highest_admin
@require_http_methods(['GET', 'HEAD', 'POST'])
def edit(request):
    obj = SEOConfiguration.objects.filter(pk=1).first()
    form = SEOConfigurationForm(request.POST if request.method == 'POST' else None, instance=obj or SEOConfiguration(pk=1))
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            LogEntry.objects.log_actions(user_id=request.user.pk, queryset=[saved], action_flag=CHANGE if obj else ADDITION,
                change_message='사이트 SEO 설정 저장')
        messages.success(request, 'SEO 설정을 저장했습니다.')
        return redirect('seo:detail')
    return render(request, 'seo/form.html', {'object': obj, 'seo': obj, 'form': form, 'form_sections': form.sections,
        'title': 'SEO 설정', 'cancel_url': reverse('seo:detail')})


@highest_admin
@require_http_methods(['GET', 'HEAD', 'POST'])
def delete(request):
    obj = SEOConfiguration.objects.filter(pk=1).first()
    if not obj:
        raise Http404
    if request.method == 'POST':
        with transaction.atomic():
            LogEntry.objects.log_actions(user_id=request.user.pk, queryset=[obj], action_flag=DELETION,
                change_message='사이트 SEO 설정 삭제: 기본 메타 정보로 복귀')
            obj.delete()
        messages.success(request, 'SEO 설정을 삭제하고 기본 메타 정보로 되돌렸습니다.')
        return redirect('seo:detail')
    return render(request, 'seo/delete.html', {'object': obj, 'seo': obj, 'cancel_url': reverse('seo:detail')})


@require_safe
def robots(request):
    if getattr(request, 'organization', None) is not None:
        raise Http404
    return HttpResponse(robots_text(request), content_type='text/plain; charset=utf-8')


@require_safe
def sitemap(request):
    if getattr(request, 'organization', None) is not None:
        raise Http404
    configuration = get_configuration()
    if not configuration.sitemap_enabled:
        raise Http404
    response = HttpResponse(sitemap_xml(request), content_type='application/xml; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=' + str(configuration.sitemap_cache_seconds)
    return response

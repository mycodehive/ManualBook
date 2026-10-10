from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('home')),
    path('health/', lambda request: JsonResponse({'status': 'ok'}), name='health'),
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls')),
    path('', include('apps.core.urls')),
    path('menus/', include('apps.menus.urls')),
    path('settings/integrations/', include('apps.integrations.urls')),
    path('manuals/', include('apps.manuals.urls')),
]

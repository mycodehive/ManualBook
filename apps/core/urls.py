from django.urls import path
from . import views
urlpatterns = [path('home/', views.home, name='home'), path('settings/', views.settings_view, name='site_settings'), path('settings/audit/', views.audit_log, name='audit_log')]

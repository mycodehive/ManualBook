from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth
from . import views
urlpatterns = [path('login/', views.OrganizationLoginView.as_view(), name='login'), path('logout/', auth.LogoutView.as_view(), name='logout'), path('accounts/profile/', views.profile, name='account_profile'), path('accounts/password/', auth.PasswordChangeView.as_view(template_name='accounts/password.html', success_url=reverse_lazy('account_profile')), name='account_password_change'), path('accounts/', views.management, name='account_management')]

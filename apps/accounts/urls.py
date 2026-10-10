from django.urls import path
from django.contrib.auth import views as auth
from . import views
urlpatterns = [path('login/', auth.LoginView.as_view(template_name='registration/login.html'), name='login'), path('logout/', auth.LogoutView.as_view(), name='logout'), path('accounts/profile/', views.profile, name='account_profile'), path('accounts/password/', auth.PasswordChangeView.as_view(template_name='accounts/password.html', success_url='/accounts/profile/'), name='account_password_change'), path('accounts/', views.management, name='account_management')]

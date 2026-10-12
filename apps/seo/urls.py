from django.urls import path
from . import views
app_name = 'seo'
urlpatterns = [path('', views.detail, name='detail'), path('edit/', views.edit, name='edit'), path('delete/', views.delete, name='delete')]

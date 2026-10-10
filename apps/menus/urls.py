from django.urls import path
from . import views
urlpatterns=[path('',views.index,name='menu_list'),path('create/',views.edit,name='menu_create'),path('<int:pk>/edit/',views.edit,name='menu_edit'),path('<int:pk>/delete/',views.delete,name='menu_delete')]

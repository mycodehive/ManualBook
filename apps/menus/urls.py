from django.urls import path
from . import views
urlpatterns=[path('',views.index,name='menu_list'),path('move/',views.move,name='menu_move'),path('export/',views.export,name='menu_export'),path('import/',views.import_file,name='menu_import'),path('create/',views.edit,name='menu_create'),path('item/<str:code>/',views.detail,name='menu_detail'),path('<int:pk>/edit/',views.edit,name='menu_edit'),path('<int:pk>/delete/',views.delete,name='menu_delete')]

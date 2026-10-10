from django.urls import path
from . import views
urlpatterns=[
    path('organizations/',views.organization_list,name='organization_list'),
    path('organizations/create/',views.organization_edit,name='organization_create'),
    path('organizations/<int:pk>/edit/',views.organization_edit,name='organization_edit'),
    path('organization/members/',views.members,name='organization_members'),
    path('organization/members/create/',views.member_edit,name='organization_member_create'),
    path('organization/members/<int:pk>/edit/',views.member_edit,name='organization_member_edit'),
    path('organization/<str:kind>/',views.directory,name='organization_directory'),
    path('organization/<str:kind>/create/',views.directory_edit,name='organization_directory_create'),
    path('organization/<str:kind>/<int:pk>/edit/',views.directory_edit,name='organization_directory_edit'),
    path('organization/<str:kind>/<int:pk>/delete/',views.directory_delete,name='organization_directory_delete'),
]

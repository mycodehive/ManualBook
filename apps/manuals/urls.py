from django.urls import path
from . import views
from . import exchange_views
app_name='manuals'
urlpatterns=[
 path('spaces/<int:pk>/import-files/', exchange_views.import_files, name='import_files'),
 path('nodes/<int:pk>/pdf/', exchange_views.export_pdf, name='export_pdf'),
 path('',views.index,name='index'),path('preview/',views.preview,name='preview'),path('spaces/',views.spaces,name='spaces'),path('spaces/create/',views.space_form,name='space_create'),
 path('spaces/<int:pk>/',views.space,name='space'),path('spaces/<int:pk>/settings/',views.space_form,name='space_settings'),path('spaces/<int:space_id>/nodes/create/',views.node_form,name='node_create'),path('spaces/<int:pk>/trash/',views.trash,name='trash'),path('spaces/<int:pk>/export/',views.export_space,name='export_space'),path('spaces/<int:pk>/import/',views.import_markdown,name='import'),
 path('nodes/<int:pk>/',views.page,name='page'),path('nodes/<int:pk>/settings/',views.node_form,name='node_settings'),path('nodes/<int:pk>/permissions/',views.permission,name='permission'),path('nodes/<int:pk>/edit/',views.edit,name='edit'),path('nodes/<int:pk>/autosave/',views.autosave,name='autosave'),path('nodes/<int:pk>/history/',views.history,name='history'),path('nodes/<int:pk>/favorite/',views.favorite,name='favorite'),path('nodes/<int:pk>/upload/',views.upload,name='upload'),path('nodes/<int:pk>/export/',views.export_page,name='export_page'),path('nodes/<int:pk>/actions/<str:action>/',views.action,name='action'),
 path('reviews/',views.reviews,name='reviews'),path('reviews/<int:pk>/',views.review_detail,name='review_detail'),path('reviews/<int:pk>/decision/',views.decision,name='decision'),path('attachments/<int:pk>/',views.download,name='download'),
]

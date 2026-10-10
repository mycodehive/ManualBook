from django.contrib import admin
from .models import Menu
@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display=['name','code','parent_menu','url','order','is_active']
    filter_horizontal=['allowed_groups']

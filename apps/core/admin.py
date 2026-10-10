from django.contrib import admin
from .models import SiteConfiguration, AuditEvent
admin.site.register(SiteConfiguration)
@admin.register(AuditEvent)
class AuditAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'actor', 'action', 'object_type', 'object_id']
    readonly_fields = ['actor','action','object_type','object_id','details','created_at']
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

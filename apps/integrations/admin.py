from django.contrib import admin
from .models import Connection, DataResource, FeatureBinding, ConfigurationRevision
from .forms import ConnectionForm, FeatureBindingForm
from .services import save_binding
@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    form=ConnectionForm
    exclude=['encrypted_secrets']
    def save_model(self,request,obj,form,change):
        if not change: obj.owner=request.user
        if form.cleaned_data.get('secrets_input') is not None: obj.set_secrets(form.cleaned_data['secrets_input'])
        super().save_model(request,obj,form,change)
admin.site.register(DataResource)
# Feature edits use the settings UI to preserve revision and audit guarantees.
@admin.register(FeatureBinding)
class BindingAdmin(admin.ModelAdmin):
    readonly_fields=['feature_code','connection','data_resource','resource_id','config','field_mapping','revision','updated_at']
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
@admin.register(ConfigurationRevision)
class RevisionAdmin(admin.ModelAdmin):
    readonly_fields=['binding','number','snapshot','created_by','created_at']
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False

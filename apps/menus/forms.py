from django import forms
from apps.organizations.forms import ScopedModelForm
from .models import Menu
class MenuForm(ScopedModelForm):
    class Meta:
        model = Menu
        fields = ['name','code','url','parent_menu','order','is_active','children_as_tabs','allowed_groups','description']
        widgets = {'allowed_groups': forms.CheckboxSelectMultiple}

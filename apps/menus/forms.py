from django import forms
from .models import Menu
class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = ['name','code','url','parent_menu','order','is_active','children_as_tabs','allowed_groups','description']
        widgets = {'allowed_groups': forms.CheckboxSelectMultiple}

import re
from django import forms
from apps.organizations.forms import ScopedModelForm
from .models import SiteConfiguration

class SiteConfigurationForm(ScopedModelForm):
    class Meta:
        model = SiteConfiguration
        fields = ['name', 'subtitle', 'logo_url', 'primary_color']
    def clean_primary_color(self):
        value = self.cleaned_data['primary_color']
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise forms.ValidationError('색상은 #2563eb 형식으로 입력하세요.')
        return value

from django import forms
from .models import Connection, DataResource, FeatureBinding
from .validation import validate_options
class ConnectionForm(forms.ModelForm):
    secrets_input = forms.JSONField(label='비밀 정보 (JSON)', required=False, widget=forms.Textarea(attrs={'rows':3}), help_text='저장 시 암호화합니다. 비워 두면 기존 비밀값을 유지합니다.')
    class Meta:
        model = Connection
        fields=['name','provider','shared','groups','active','config']
        widgets={'groups':forms.CheckboxSelectMultiple}
    def clean_secrets_input(self):
        value=self.cleaned_data.get('secrets_input')
        if value is not None and not isinstance(value,dict): raise forms.ValidationError('JSON 객체를 입력하세요.')
        return value
class DataResourceForm(forms.ModelForm):
    class Meta:
        model=DataResource
        fields=['connection','name','external_id','config','schema']
class FeatureBindingForm(forms.ModelForm):
    revision_token = forms.IntegerField(required=False, widget=forms.HiddenInput)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['revision_token'].initial = self.instance.revision if self.instance.pk else 0
        self.fields['revision_token'].required = bool(self.instance.pk)

    class Meta:
        model=FeatureBinding
        fields=['feature_code','connection','data_resource','resource_id','config','field_mapping']

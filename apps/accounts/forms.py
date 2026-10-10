from django import forms
from django.contrib.auth import get_user_model
class ProfileForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name','last_name','email']


class IdentityPolicyForm(forms.ModelForm):
    reserved_usernames = forms.CharField(label='사용자 생성 금지 아이디', required=False,
        widget=forms.Textarea(attrs={'rows': 10}),
        help_text='줄바꿈 또는 쉼표로 구분하세요. 대소문자를 구분하지 않고 중복을 제거합니다. 기존 계정의 로그인에는 영향을 주지 않습니다.')
    class Meta:
        from .models import IdentityPolicy
        model = IdentityPolicy
        fields = ['reserved_usernames']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial['reserved_usernames'] = '\n'.join(self.instance.reserved_usernames)
    def clean_reserved_usernames(self):
        import re
        from .identity import validate_policy_usernames
        return validate_policy_usernames([value.strip() for value in re.split(r'[,\r\n]+', self.cleaned_data['reserved_usernames']) if value.strip()])

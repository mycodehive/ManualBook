from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from .identity import validate_public_username


class IdentityUserCreationForm(AdminUserCreationForm):
    def clean_username(self):
        return validate_public_username(self.cleaned_data['username'])


class IdentityUserChangeForm(UserChangeForm):
    def clean_username(self):
        value = self.cleaned_data['username']
        if self.instance.pk and value != self.instance.username:
            raise ValidationError('기존 계정의 아이디는 변경할 수 없습니다.')
        return value


class IdentityUserAdmin(UserAdmin):
    add_form = IdentityUserCreationForm
    form = IdentityUserChangeForm


User = get_user_model()
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, IdentityUserAdmin)

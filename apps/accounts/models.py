from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .identity import default_reserved_usernames, normalize_username, validate_policy_usernames


class PublicIdentity(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='public_identity')
    public_username = models.CharField('로그인 아이디', max_length=150)
    normalized_username = models.CharField(max_length=150, unique=True, editable=False)

    def save(self, *args, **kwargs):
        self.normalized_username = normalize_username(self.public_username)
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.public_username


class IdentityPolicy(models.Model):
    reserved_usernames = models.JSONField('예약 아이디', default=default_reserved_usernames, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.pk not in (None, 1):
            raise ValidationError('아이디 정책은 한 개만 등록할 수 있습니다.')
        try:
            self.reserved_usernames = validate_policy_usernames(self.reserved_usernames)
        except ValidationError as exc:
            raise ValidationError({'reserved_usernames': exc.messages})


    def save(self, *args, **kwargs):
        self.pk = 1
        self.full_clean()
        return super().save(*args, **kwargs)

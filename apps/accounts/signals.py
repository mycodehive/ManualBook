from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .identity import ensure_identity, validate_public_username, normalize_username


@receiver(pre_save, sender=settings.AUTH_USER_MODEL)
def validate_user_identity(sender, instance, raw=False, **kwargs):
    if raw:
        return
    if instance.pk:
        old_username = sender.objects.filter(pk=instance.pk).values_list('username', flat=True).first()
        if old_username is not None and old_username != instance.username:
            raise ValidationError('기존 계정의 아이디는 변경할 수 없습니다.')
        return
    if not instance.is_superuser:
        validate_public_username(instance.username)
    else:
        from .models import PublicIdentity
        normalized = normalize_username(instance.username)
        if PublicIdentity.objects.filter(normalized_username=normalized).exists() or sender.objects.filter(username__iexact=instance.username).exists():
            raise ValidationError('이미 사용 중인 아이디입니다. 다른 아이디를 사용해주세요.')


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def register_public_identity(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        ensure_identity(instance)

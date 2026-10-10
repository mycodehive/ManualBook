"""One public identity namespace and one configurable username policy."""
import re
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

RESERVED_MESSAGE = '시스템에서 예약된 아이디입니다. 다른 아이디를 사용해주세요.'
DUPLICATE_MESSAGE = '이미 사용 중인 아이디입니다. 다른 아이디를 사용해주세요.'


def default_reserved_usernames():
    return ['admin', 'administrator', 'admins', 'manager', 'superadmin', 'root', 'superuser', 'sysadmin']


def normalize_username(value):
    return str(value or '').strip().casefold()


def validate_policy_usernames(values):
    if not isinstance(values, list):
        raise ValidationError('예약 아이디는 문자열 목록으로 입력하세요.')
    normalized = []
    for value in values:
        if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9_.@+-]{1,100}', normalize_username(value)):
            raise ValidationError('예약 아이디는 영문·숫자·_.@+- 문자 1~100자로 입력하세요.')
        normalized.append(normalize_username(value))
    return sorted(set(normalized))


def validate_public_username(value, user=None):
    from .models import IdentityPolicy, PublicIdentity
    normalized = normalize_username(value)
    if not re.fullmatch(r'[a-z0-9_.@+-]{1,100}', normalized):
        raise ValidationError('아이디는 영문·숫자·_.@+- 문자 1~100자로 입력하세요.')
    policy = IdentityPolicy.objects.filter(pk=1).first()
    reserved = policy.reserved_usernames if policy else default_reserved_usernames()
    if normalized in {normalize_username(item) for item in reserved}:
        raise ValidationError(RESERVED_MESSAGE)
    identities = PublicIdentity.objects.filter(normalized_username=normalized)
    users = get_user_model().objects.filter(username__iexact=normalized)
    if user and user.pk:
        identities = identities.exclude(user=user)
        users = users.exclude(pk=user.pk)
    if identities.exists() or users.exists():
        raise ValidationError(DUPLICATE_MESSAGE)
    return normalized


@transaction.atomic
def ensure_identity(user):
    """Publish a new raw auth username; legacy aliases are only assigned by migration."""
    from .models import PublicIdentity
    identity = PublicIdentity.objects.filter(user=user).first()
    if identity:
        return identity
    normalized = normalize_username(user.username)
    if not normalized or len(normalized) > 150:
        raise ValidationError('계정 아이디 형식이 올바르지 않습니다.')
    identity = PublicIdentity(user=user, public_username=user.username, normalized_username=normalized)
    identity.save()
    return identity


@transaction.atomic
def create_identity_user(username, **attrs):
    username = validate_public_username(username)
    user = get_user_model().objects.create_user(username=username, **attrs)
    ensure_identity(user)
    return user

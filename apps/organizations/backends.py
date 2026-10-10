import re
from django.core.exceptions import ValidationError
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from apps.accounts.identity import normalize_username
from apps.accounts.models import PublicIdentity
from .models import Membership
from .scoping import current_organization


def organization_username(organization, local_name):
    """Legacy fixture/import helper; new registration uses create_identity_user."""
    if not re.fullmatch(r'[A-Za-z0-9_.@+-]{1,100}', local_name or ''):
        raise ValidationError('아이디 형식이 올바르지 않습니다.')
    return 'org' + str(organization.pk) + '__' + local_name


class OrganizationBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if username is None or password is None:
            return None
        identity = PublicIdentity.objects.select_related('user').filter(normalized_username=normalize_username(username)).first()
        if not identity:
            # Match Django's nonexistent-user password hashing timing protection.
            get_user_model()().set_password(password)
            return None
        user = identity.user
        if not user.check_password(password) or not self.user_can_authenticate(user):
            return None
        org = getattr(request, 'organization', None) or current_organization()
        if org:
            if not org.active:
                return None
            if user.is_superuser or Membership.all_objects.filter(organization=org, user=user, active=True).exists():
                return user
            return None
        if user.is_superuser or Membership.all_objects.filter(user=user, active=True, organization__active=True).exists():
            return user
        return None

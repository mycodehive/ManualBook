import json
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from apps.organizations.scoping import ScopedModel, current_organization, is_org_admin, organization_group_ids


def cipher():
    key = settings.INTEGRATION_ENCRYPTION_KEY
    if not key:
        raise ValidationError('서버의 INTEGRATION_ENCRYPTION_KEY를 먼저 설정해 주세요.')
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        raise ValidationError('암호화 키 형식이 올바르지 않습니다.') from None


class Connection(ScopedModel):
    PROVIDERS = [('notion', 'Notion'), ('google', 'Google'), ('smtp', '메일 SMTP'), ('sms', '문자'), ('llm', 'LLM')]
    name = models.CharField('연결명', max_length=120)
    provider = models.CharField('서비스', max_length=20, choices=PROVIDERS)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    shared = models.BooleanField('조직 공유', default=False)
    groups = models.ManyToManyField(Group, blank=True, verbose_name='사용 그룹')
    active = models.BooleanField('사용', default=True)
    config = models.JSONField('일반 옵션', default=dict, blank=True)
    encrypted_secrets = models.TextField(blank=True, editable=False)
    status = models.CharField(max_length=30, default='UNTESTED')
    last_test_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        from .validation import validate_options
        validate_options(self.config)
        if self.provider == 'smtp' and self.config.get('security','starttls') not in ('ssl','starttls'):
            raise ValidationError('메일 보안 방식은 ssl 또는 starttls여야 합니다.')

    def set_secrets(self, values):
        if not isinstance(values, dict) or len(json.dumps(values)) > 65536:
            raise ValidationError('비밀값은 64KB 이하 JSON 객체여야 합니다.')
        self.encrypted_secrets = cipher().encrypt(json.dumps(values).encode()).decode() if values else ''

    def secrets(self):
        if not self.encrypted_secrets:
            return {}
        try:
            return json.loads(cipher().decrypt(self.encrypted_secrets.encode()))
        except InvalidToken:
            raise ValidationError('연결 비밀값을 읽을 수 없습니다. 암호화 키를 확인해 주세요.') from None

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization','name'], name='connection_organization_name')]

    def can_use(self, user=None):
        org = current_organization()
        if not org or self.organization_id != org.pk: return False
        from apps.organizations.models import Membership
        if user and not user.is_superuser and not Membership.objects.filter(user=user,active=True).exists(): return False
        if not user or not user.is_authenticated or not user.is_active or not self.active:
            return False
        if user and user.is_authenticated and (is_org_admin(user) or self.owner_id == user.pk):
            return True
        if not self.shared:
            return False
        groups = self.groups.all()
        if not groups.exists():
            return bool(user and user.is_authenticated)
        return bool(user and user.is_authenticated and groups.filter(pk__in=organization_group_ids(user)).exists())

    def __str__(self):
        return self.name


class DataResource(ScopedModel):
    connection = models.ForeignKey(Connection, on_delete=models.PROTECT, related_name='resources')
    name = models.CharField('자원명', max_length=120)
    external_id = models.CharField('DB / Sheet ID 또는 공개 CSV URL', max_length=600)
    config = models.JSONField('자원 옵션', default=dict, blank=True)
    schema = models.JSONField(default=dict, blank=True)
    def clean(self):
        super().clean()
        from .validation import validate_options
        validate_options(self.config)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['connection', 'name'], name='resource_connection_name')]
    def __str__(self):
        return self.name


class FeatureBinding(ScopedModel):
    feature_code = models.CharField('기능 코드', max_length=70)
    connection = models.ForeignKey(Connection, null=True, blank=True, on_delete=models.PROTECT, related_name='bindings')
    data_resource = models.ForeignKey(DataResource, null=True, blank=True, on_delete=models.PROTECT, related_name='bindings')
    resource_id = models.CharField('직접 DB / Sheet ID', max_length=600, blank=True)
    config = models.JSONField('업무 옵션', default=dict, blank=True)
    field_mapping = models.JSONField('필드 매핑', default=dict, blank=True)
    revision = models.PositiveIntegerField(default=0, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    def clean(self):
        super().clean()
        from .validation import validate_options
        from apps.menus.registry import FEATURES
        validate_options(self.config)
        validate_options(self.field_mapping)
        feature = FEATURES.get(self.feature_code)
        if feature and feature.connection_kind and self.connection and self.connection.provider != feature.connection_kind:
            raise ValidationError('기능의 서비스 종류와 연결이 다릅니다.')
        if self.resource_id and self.data_resource:
            raise ValidationError('등록 자원과 직접 ID 중 하나만 선택하세요.')
        if self.data_resource and self.data_resource.connection_id != self.connection_id:
            raise ValidationError('선택 자원과 연결 계정이 다릅니다.')
        for value in (self.config, self.field_mapping):
            if not isinstance(value, dict):
                raise ValidationError('설정은 JSON 객체여야 합니다.')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization','feature_code'], name='binding_organization_feature')]
    def __str__(self):
        return self.feature_code


class ConfigurationRevision(ScopedModel):
    binding = models.ForeignKey(FeatureBinding, on_delete=models.CASCADE, related_name='versions')
    number = models.PositiveIntegerField()
    snapshot = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['binding','number'], name='binding_revision_number')]



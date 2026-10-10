from django.contrib.auth.models import Group
from django.db import models
from apps.organizations.scoping import ScopedModel


def validate_menu_url(value):
    from django.core.exceptions import ValidationError
    from django.core.validators import URLValidator
    if any(ord(char) < 32 or ord(char) == 127 for char in value) or '\\' in value:
        raise ValidationError('메뉴 URL에 제어 문자나 역슬래시를 사용할 수 없습니다.')
    if not value or value == '#' or (value.startswith('/') and not value.startswith('//')):
        return
    if not value.lower().startswith(('https://', 'http://')):
        raise ValidationError('내부 경로(/로 시작) 또는 http://, https:// 외부 URL을 입력하세요.')
    URLValidator(schemes=['http', 'https'])(value)


class Menu(ScopedModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    url = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    parent_menu = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
    )
    is_active = models.BooleanField(default=True)
    children_as_tabs = models.BooleanField('하위 메뉴를 탭으로 표시', default=False, help_text='좌측 메뉴는 유지하고 콘텐츠 상단에 접근 가능한 하위 메뉴를 탭으로 표시합니다.')
    allowed_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name='allowed_menus',
        verbose_name='허용 그룹',
        help_text='비어있으면 모든 로그인 사용자에게 표시됩니다.',
    )
    inherited_group_rules = models.JSONField(default=list, blank=True, editable=False)
    description = models.TextField(blank=True)
    workspace_dir_name = models.CharField(max_length=100, blank=True)
    workspace_path = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('order', 'name')
        constraints = [models.UniqueConstraint(fields=['organization','code'], name='menu_organization_code')]

    def __str__(self):
        return f'{self.name} ({self.code})'

    @property
    def navigation_url(self):
        from django.core.exceptions import ValidationError
        try:
            validate_menu_url(self.url)
        except ValidationError:
            return '#'
        from django.urls import get_script_prefix
        return get_script_prefix().rstrip('/') + self.url if self.url.startswith('/') else self.url

    @property
    def is_external(self):
        return self.navigation_url.lower().startswith(('http://', 'https://'))

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        self.url = self.url.strip()
        try:
            validate_menu_url(self.url)
        except ValidationError as exc:
            raise ValidationError({'url': exc.messages}) from exc
        seen = {self.pk} if self.pk else set()
        parent = self.parent_menu
        depth = 1
        while parent is not None:
            if parent.pk in seen:
                raise ValidationError({'parent_menu': '자기 자신이나 하위 메뉴를 상위 메뉴로 선택할 수 없습니다.'})
            seen.add(parent.pk)
            depth += 1
            if depth > 3:
                raise ValidationError({'parent_menu': '메뉴는 최대 3단계까지 구성할 수 있습니다.'})
            parent = parent.parent_menu
        def height(node, visited):
            if node.pk in visited:
                raise ValidationError({'parent_menu': '메뉴 계층에 순환 참조가 있습니다.'})
            children = list(node.children.all()) if node.pk else []
            return 1 + max((height(child, visited | {node.pk}) for child in children), default=0)
        if depth + height(self, set()) - 1 > 3:
            raise ValidationError({'parent_menu': '하위 메뉴를 포함해 최대 3단계까지 구성할 수 있습니다.'})


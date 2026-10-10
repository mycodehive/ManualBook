from django.conf import settings
from django.db import models
from apps.organizations.scoping import ScopedModel

class SiteConfiguration(ScopedModel):
    name = models.CharField('조직명', max_length=120, default='ManualBook')
    subtitle = models.CharField('설명', max_length=200, default='함께 만들고 공유하는 사내 매뉴얼')
    logo_url = models.URLField('로고 URL', blank=True)
    primary_color = models.CharField('강조색', max_length=7, default='#355fe5')
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization'], name='site_configuration_organization')]

class AuditEvent(ScopedModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

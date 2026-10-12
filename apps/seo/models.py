import re
from urllib.parse import urlsplit
from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


def validate_https_url(value, base=False):
    if not value:
        return
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValidationError('인증 정보가 없는 HTTPS 주소를 입력하세요.')
    try:
        parsed.port
    except ValueError:
        raise ValidationError('올바른 포트 번호를 입력하세요.')
    if parsed.fragment or (base and (parsed.path not in ('', '/') or parsed.query)):
        raise ValidationError('사이트 주소에는 경로·쿼리·프래그먼트를 포함할 수 없습니다.' if base else '이미지 주소에는 프래그먼트를 포함할 수 없습니다.')


class SEOConfiguration(models.Model):
    site_url = models.URLField('사이트 대표 주소', max_length=2048, blank=True)
    title = models.CharField('소개 페이지 제목', max_length=200, default='ManualBook · 팀의 업무 기준을 한곳에')
    description = models.CharField('소개 페이지 설명', max_length=500, default='업무 절차와 안내 문서를 한곳에 정리하세요. 조직별 공간, 문서 편집, 검토·승인, 버전 관리와 공개 가이드 공유를 제공합니다.')
    keywords = models.CharField('검색 키워드', max_length=500, blank=True)
    generator_enabled = models.BooleanField('Generator 메타 태그 사용', default=False)
    generator_content = models.CharField('Generator 내용', max_length=100, default='ManualBook')
    og_site_name = models.CharField('Open Graph 사이트 이름', max_length=100, default='ManualBook')
    og_image_url = models.URLField('Open Graph 이미지 주소', max_length=2048, blank=True)
    og_image_width = models.PositiveIntegerField('이미지 너비(px)', null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(8192)])
    og_image_height = models.PositiveIntegerField('이미지 높이(px)', null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(8192)])
    twitter_card = models.CharField('Twitter 카드 유형', max_length=30, choices=[('summary', '요약'), ('summary_large_image', '큰 이미지 요약')], default='summary_large_image')
    twitter_handle = models.CharField('Twitter 계정', max_length=16, blank=True)
    sitemap_enabled = models.BooleanField('사이트맵 사용', default=True)
    sitemap_cache_seconds = models.PositiveIntegerField('사이트맵 캐시 시간(초)', default=3600, validators=[MaxValueValidator(86400)])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(pk=1), name='seo_configuration_singleton')]
        verbose_name = 'SEO 설정'

    def clean(self):
        errors = {}
        for field, base in [('site_url', True), ('og_image_url', False)]:
            try:
                validate_https_url(getattr(self, field), base=base)
            except (ValidationError, ValueError) as exc:
                errors[field] = exc.messages if isinstance(exc, ValidationError) else ['올바른 URL을 입력하세요.']
        if self.site_url:
            self.site_url = self.site_url.rstrip('/')
        if bool(self.og_image_width) != bool(self.og_image_height):
            errors['og_image_width'] = '이미지 너비와 높이를 함께 입력하세요.'
        if (self.og_image_width or self.og_image_height) and not self.og_image_url:
            errors['og_image_url'] = '이미지 크기를 지정하려면 이미지 주소를 입력하세요.'
        if self.twitter_handle and not re.fullmatch(r'@[A-Za-z0-9_]{1,15}', self.twitter_handle):
            errors['twitter_handle'] = '@로 시작하는 영문·숫자·밑줄 계정을 입력하세요.'
        if self.pk not in (None, 1):
            errors['__all__'] = 'SEO 설정은 한 개만 등록할 수 있습니다.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk is None:
            self.pk = 1
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return '사이트 SEO 설정'

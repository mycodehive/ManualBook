from django import forms
from .models import SEOConfiguration


class SEOConfigurationForm(forms.ModelForm):
    class Meta:
        model = SEOConfiguration
        fields = ['site_url', 'title', 'description', 'keywords', 'generator_enabled', 'generator_content',
            'og_site_name', 'og_image_url', 'og_image_width', 'og_image_height', 'twitter_card', 'twitter_handle',
            'sitemap_enabled', 'sitemap_cache_seconds']
        widgets = {'description': forms.Textarea(attrs={'rows': 3}), 'keywords': forms.Textarea(attrs={'rows': 2})}
        help_texts = {
            'site_url': '예: https://manualbook.example.com — 경로 없이 입력합니다. 비워 두면 현재 요청 주소를 사용합니다.',
            'keywords': '쉼표로 구분합니다. 키워드 메타 태그가 검색 순위를 보장하지는 않습니다.',
            'generator_enabled': '사용할 때만 Generator 메타 태그를 출력합니다.',
            'og_image_url': '외부 이미지를 저장하거나 가져오지 않습니다. HTTPS 이미지 URL을 입력합니다. 비워 두면 기본 소개 이미지를 사용합니다.',
            'og_image_width': '이미지 크기는 실제 너비·높이를 함께 입력하세요. 1~8192px.',
            'twitter_handle': '선택 사항. 예: @manualbook',
            'sitemap_enabled': '현재 사이트맵은 전역 소개 페이지 한 개만 포함합니다. 조직 매뉴얼은 포함하지 않습니다.',
            'sitemap_cache_seconds': '응답의 Cache-Control 시간입니다. 브라우저·프록시 캐시 TTL이며 예약 생성 기능은 아닙니다. 0~86400초.',
        }

    @property
    def sections(self):
        groups = [('기본 메타 정보', '소개 페이지의 제목과 설명, 대표 주소를 설정합니다.', ['site_url', 'title', 'description', 'keywords']),
            ('Generator', '제품 식별 메타 태그 출력 여부를 설정합니다.', ['generator_enabled', 'generator_content']),
            ('Open Graph', '링크를 공유할 때 사용하는 사이트 이름과 이미지를 설정합니다.', ['og_site_name', 'og_image_url', 'og_image_width', 'og_image_height']),
            ('Twitter 카드', '공유 카드 유형과 계정을 설정합니다.', ['twitter_card', 'twitter_handle']),
            ('사이트맵', '검색 엔진에 소개 페이지 주소를 제공하는 설정입니다.', ['sitemap_enabled', 'sitemap_cache_seconds'])]
        return [{'title': title, 'description': description, 'fields': [self[name] for name in names]} for title, description, names in groups]

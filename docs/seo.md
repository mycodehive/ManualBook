# SEO 설정

사이트 최고관리자는 전체 조직 관리 화면의 **SEO 설정** 버튼 또는 `/organizations/seo/`에서 사이트 공통 SEO 설정을 등록·조회·수정·삭제합니다. 조직 관리자, 일반 사용자, staff 계정은 접근할 수 없습니다. 최고관리자도 조직 주소 하위에서는 공통 SEO 설정을 변경할 수 없습니다.

설정 항목은 사이트 기본 URL, 제목·설명·키워드, Generator 표시, Open Graph 사이트명·공유 이미지 URL·크기, Twitter 카드·계정, Sitemap 사용 여부 및 사이트맵 응답 캐시 시간입니다. 공유 이미지는 직접 업로드하거나 공개 HTTPS 이미지 주소를 입력합니다. 업로드 이미지를 우선 사용하며 업로드 이미지를 지우면 입력한 URL, URL도 없으면 기본 소개 이미지를 사용합니다. URL을 저장해도 서버가 외부 이미지를 가져오지 않습니다.

업로드는 PNG·JPEG·WebP, 최대 5MB를 지원합니다. 실제 이미지 형식과 크기를 검사하고 PNG로 다시 저장하여 원본 메타데이터를 제거합니다. 업로드 이미지 크기는 자동 반영합니다. 현재 공유 이미지는 로그인 없이 `/seo-images/<임의 UUID>/`에서 제공되며 이 이미지에 개인정보나 비공개 문서 내용을 넣지 마세요. 조직 매뉴얼 첨부파일과 다른 파일은 공개하지 않습니다. 교체·제거·설정 삭제 시 이전 공유 파일을 정리합니다. 공유 파일은 기존 `DJANGO_MEDIA_ROOT` 아래에 저장하므로 웹 서비스 계정에 해당 경로 쓰기 권한이 필요하며, 업로드 파일 백업에 포함해야 합니다.

메타데이터는 공개 소개 페이지 `/intro`, `/intro/`에 적용합니다. canonical과 공유 URL은 설정한 사이트 기본 URL의 `/intro/`로 통일합니다. 설정 삭제는 기본 소개 메타데이터로 되돌리며 조직·사용자·매뉴얼을 삭제하지 않습니다.

`/sitemap.xml`에는 소개 페이지 URL만 포함합니다. 조직별 공간과 문서, 관리자·로그인 URL은 포함하지 않습니다. Sitemap을 끄면 `/sitemap.xml`은 404를 반환하고 robots.txt의 Sitemap 안내도 제거합니다. 매 요청에 현재 설정으로 생성하므로 별도 예약 작업이나 생성 버튼은 필요하지 않습니다. 캐시 시간은 Sitemap 응답의 브라우저·프록시 캐시 유효 시간이며 DB 메타데이터 갱신 주기가 아닙니다.

소개 페이지와 robots/Sitemap을 제외한 Django 응답에는 `X-Robots-Tag: noindex, nofollow`를 적용하고 공통 내부 화면에도 robots 메타 태그를 제공합니다. 이는 검색엔진에 대한 지침입니다. 데이터 보안은 기존 로그인·조직·문서 권한 검사가 계속 담당합니다. User-Agent에 따라 권한이나 문서 내용이 달라지지 않습니다.

생성·수정·삭제는 최고관리자 권한 및 CSRF 검증을 거친 POST 요청으로 처리합니다. 삭제는 확인 화면을 제공하며 변경은 감사 기록에 남습니다.

## 운영 반영

코드 업데이트 후 기존 운영 환경에서 실행합니다.

```bash
uv run --frozen python manage.py migrate
uv run --frozen python manage.py collectstatic --noinput
```

웹 서비스를 재시작한 뒤 최고관리자로 설정을 등록하고 `/intro/`, `/robots.txt`, `/sitemap.xml`의 결과를 확인합니다. SEO 설정은 검색 순위나 색인 완료를 보장하지 않습니다. 검색엔진의 재수집 및 외부 캐시 갱신에는 시간이 걸릴 수 있습니다.

참고: https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag

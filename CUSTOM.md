# Platform customization

- 공통 레이아웃: `templates/base.html`, `templates/partials/`, `static/css/base.css`, `static/js/platform.js`.
- 조직 관리자 UI에서 브랜딩, 사용자/그룹, 3단 메뉴, connection/resource/feature binding을 관리한다.
- source `iacfgeneral_ver3` 업무 데이터, 로고, 비밀, 하드코딩된 그룹/코드는 가져오지 않는다.
- bootstrap는 (organization,code) 기준으로 없는 기본 메뉴만 만든다. 메뉴 이름/URL을 바꿀 때 기존 레코드를 덮어쓰는 data migration을 피한다.
- 새로운 도메인은 자체 app/service/policy와 stable feature code로 연결하고 core에서 도메인 모델을 직접 import하지 않는다.
- 비밀은 encrypted connection fields, ordinary options는 JSON. 비밀을 export/audit/template에 포함하지 않는다.
- 운영 배포 지침은 `docs/operations.md`, 제품/보안/로드맵은 `docs/planning/`.

참조 UI 자산을 적용한 사실과 픽셀 비교 완료는 별개다. 브라우저 검증 결과를 확인하여 디자인 변경 범위를 보고한다.

- Tenant 모델은 ScopedModel을 상속하고 조회는 objects를 사용한다. all_objects와 직접 SQL은 전역 관리/이관 용도로만 사용한다.
- 조직 정책은 Membership와 OrganizationGroup에서 판단하며 전역 auth.User.groups/is_staff로 조직 권한을 판정하지 않는다.
- 새 ForeignKey/M2M/파일 기능에는 교차 조직 읽기·쓰기 거부 테스트를 추가한다. URL은 reverse 또는 url template tag로 조직 prefix를 유지한다.

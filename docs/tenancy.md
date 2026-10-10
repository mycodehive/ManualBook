# 조직 격리 설계

## 권한과 주소
- 사이트 최고 관리자: Django superuser, 모든 조직을 등록·활성화·비활성화하고 조직별 화면으로 진입.
- 조직 관리자: Membership.role=admin, 자기 조직의 사용자·부서·그룹·매뉴얼·설정 관리. 전역 is_staff/is_superuser를 부여할 수 없음.
- 조직 사용자: 활성 Membership와 조직 그룹 및 문서 ACL에 따라 접근.
- 전역 console /organizations/, 최고 관리자 로그인 /login/, tenant /o/<slug>/login/, /o/<slug>/organization/members/, departments/, groups/.
- 조직 사용자 이름은 DB에서 org<id>__<name>으로 구분; 조직 로그인은 짧은 이름. 기존 legacy 계정은 기존 이름 유지.

## 경계
OrganizationMiddleware는 활성 조직 및 활성 멤버십을 확인한 뒤 ContextVar에 조직을 설정합니다. 요청 종료 및 예외에서 컨텍스트와 URL prefix를 복구하며 streaming 응답도 해당 조직 컨텍스트에서 처리합니다. 조직 응답은 private,no-store 및 Vary:Cookie를 설정합니다.
기본 ScopedManager는 현재 organization_id만 반환하고 컨텍스트가 없으면 빈 queryset을 반환합니다. 저장에는 명시적 조직 컨텍스트가 필요합니다. all_objects는 최고 관리자 console·이관·내부 관계 검증에서만 사용합니다.
모든 문서와 설정 관련 FK는 동일 조직을 검증하며 조직 소유권 변경을 거부합니다. M2M 그룹도 동일 조직이어야 합니다. 각 auth.Group은 하나의 OrganizationGroup에만 연결됩니다. 권한은 전역 user.groups를 사용하지 않고 해당 Membership.groups를 사용합니다.
문서 노드의 parent/space/draft/published, 검토 revision, 첨부 revision/node 일치를 읽기에서도 확인합니다. 손상된 참조는 최고 관리자에게도 노출하지 않습니다. 첨부파일은 private_media에 저장하고 인증된 다운로드 뷰를 거칩니다. nginx private media 직접 제공은 금지합니다. 외부 이미지와 다른 조직 이미지 URL은 정제에서 제거합니다.
조직 관리자 등록·수정 폼은 전역 권한 필드를 허용하지 않습니다. 기존 계정의 비밀번호와 개인정보를 다른 조직 관리자가 변경하지 못합니다. 로그인은 DB에 해시 키로 실패 횟수를 저장해 조직·아이디별 5회, 조직·IP별 20회에 도달하면 15분간 제한합니다. 성공해도 IP 실패 카운터는 초기화하지 않습니다. 원시 아이디·IP를 저장하지 않습니다. 신뢰된 직접 연결 프록시 IP에서만 nginx가 덮어쓴 X-Real-IP를 사용합니다. 최고 관리자 인증은 전역 로그인에서만 허용하고 이후 모든 조직으로 전환할 수 있습니다. 세션·CSRF·HTTPS 설정은 기존 enterprise 설정을 유지합니다.

## 저장소와 운영
조직은 하나의 PostgreSQL DB에서 organization_id로 분리됩니다. 물리적으로 별도 DB를 제공하거나 PostgreSQL RLS를 적용한 구조는 아닙니다. ORM 범위와 관계 검증·읽기 무결성 검증이 현재 격리 경계입니다. 직접 SQL 및 all_objects는 신뢰된 운영 코드에서만 사용해야 합니다.
배포 전에 DB/private_media 백업 및 이관 복구 훈련을 수행합니다. organizations.0002_legacy는 기존 사용자·그룹을 legacy에 매핑하고 각 앱의 후속 migration은 기존 데이터의 조직 FK를 채웁니다.
운영 확장: DB RLS·조직별 저장소·SSO/MFA·외부 보안 점검·부하 테스트는 별도 작업입니다.

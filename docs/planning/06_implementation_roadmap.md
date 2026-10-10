# 개발 로드맵

공수는 한 단계의 상대 복잡도(S/M/L), 일정 약속이 아니다. 첫 구현과 운영 릴리스는 구분한다.

| 단계 | 목표·산출물 | 선행/DB 변경 | 수용·검증 | 롤백 | 공수 |
|---|---|---|---|---|---|
| P0 | 이 8개 계획·ADR·미정사항 | 요구/참조 조사 | 도메인/플랫폼 분리 합의 | 문서 수정 | S |
| P1 | Django/uv/auth/공통 셸/CI | P0; core/accounts/menus | 빈 DB migrate+bootstrap+로그인 | 코드 회귀·미사용 DB 폐기 | M |
| P2 | 공간/트리 CRUD | P1; Space/Node | 순환/다른 공간 부모/권한 차단 | 백업 복원, 단순 역migration은 검증 후 | M |
| P3 | 열람·테마·브랜딩·TOC | P2; 사이트 설정 | 참조 셸, 모바일, 키보드 검증 | UI release 회귀 | M |
| P4 | Markdown/draft/첨부/충돌 | P2; Revision/Attachment | XSS/직접 파일/동시 수정 검사 | DB+첨부 복구 | L |
| P5 | 중앙 정책/그룹 권한 | P1~4; 그룹 M2M | URL/검색/첨부 동일 정책 | fail closed 유지 | L |
| P6 | 승인/반려/게시/이력 | P4~5; ApprovalRequest | 정확한 버전, 본인승인, 게시/초안 분리 | 이전 코드 호환 확인·DB snapshot | L |
| P7 | 검색/Markdown export | P6; 필요한 인덱스 | 한국어 기본 부분검색 및 권한 | 색인 재구축/코드 회귀 | M |
| P8 | 관리·감사·운영 자료 | P1~7; Audit/Connection/Resource/Binding | secret 암호화, 백업 복원 훈련 | DB·media·키 동시 복원 | L |
| P9 | 보안·접근성·성능·E2E | P8; 파괴적 변경 지양 | PostgreSQL·HTTPS·부하·운영 gate | maintenance+검증된 복구 | L |
| P10 | SSO/AI/RAG/API/협업 | 별도 ADR | scope/개인정보/평가 합의 | 기능 off 및 데이터 보존 | L |

## 다음 티켓
1. PostgreSQL에서 다중 작성자/승인자 트랜잭션과 optimistic locking 검증.
2. 노드별 ACL 관리 UI와 deny·상속 진리표 회귀 확대.
3. Tiptap 고급 서식 보존/드래그 트리와 접근성 E2E.
4. DOCX/ZIP import 및 PDF export의 격리 worker/총 중첩 해제량/시간 제한.
5. 한국어 검색 대표 질의 데이터와 index 성능 비교.
6. 운영자 계정 MFA/로그인 rate limit 및 observability.

운영 진입 기준은 구현된 기능 테스트 통과, 미구현 기능 공개적 명시, PostgreSQL restore 성공, 비공개 media/HTTPS, 책임자·RPO/RTO 확정이다.

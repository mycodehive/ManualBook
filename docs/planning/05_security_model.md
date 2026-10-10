# 보안 모델

## 역할 매트릭스
| 행동 | 미인증 | 열람 그룹 | 편집 그룹 | 관리·승인 그룹 | superuser |
|---|---|---|---|---|---|
| 허용 공간 게시본/검색 | 거부 | 허용 | 허용 | 허용 | 허용 |
| 초안/리비전 | 거부 | 거부 | 허용 | 허용 | 허용 |
| 생성/수정 | 거부 | 거부 | 허용 | 허용 | 허용 |
| 승인/게시/권한관리 | 거부 | 거부 | 거부 | 허용 | 허용 |
| 비공개 첨부 | 거부 | 게시 문서 범위 | 문서 접근 범위 | 문서 접근 범위 | 허용 |
| 시스템 설정 | 거부 | 거부 | 거부 | 별도 시스템 권한 | 허용 |

기본 거부. 메뉴 숨김과 도메인 권한 모두 검사한다. 자기승인은 공간 정책으로 제한한다. 비활성·보관·삭제 공간/상위 노드가 하위 URL에서 우회되지 않는지 테스트한다. 노드별 사용자/그룹 assignment가 모델에 구현되고 조상 전체 deny 우선 평가. 공간 열람 권한을 우회하는 allow는 거부한다. 노드 설정에서 ACL을 관리한다.

## 위협 및 통제
| 위협 | 통제/릴리스 검증 |
|---|---|
| IDOR | 모든 문서/리비전/다운로드/검색/내보내기 동일 권한 정책 |
| 초안 누출 | 일반 열람에서 게시 revision만 조회, 첨부와 snippet도 동일 경계 |
| XSS | Markdown 변환 이후 HTML allowlist, script/event/javascript URL 제거 |
| CSRF | 변경은 POST, Django CSRF middleware, 토큰 없는 요청 403 |
| SSRF | 초기 외부 URL fetch 미제공; 향후 private IP/DNS rebinding/redirect 검사 |
| 파일 실행 | 용량·확장자·content disposition, private storage, 공개 Nginx 경로 없음 |
| ZIP bomb | ZIP import는 경로/링크/암호화 거부, 항목수100·압축률100배·해제20MB 제한; nested DOCX 전체 자원/시간 budget은 추가 검증 |
| 토큰 노출 | Fernet 암호화, secret 입력 미반환, audit/export/log 제외 |
| 세션 탈취 | HTTPS, secure cookies, 정확한 hosts/origins 및 proxy 경계 |
| 비밀번호 공격 | Django 정책; 인터넷 운영 전 proxy/IdP 속도제한·MFA 검토 |

## 운영 보안
`.env`는 서비스 계정/운영자만 읽고 git 제외. 키를 잃으면 연결 비밀 복구 불가. 회전은 이전 키로 복호화 후 새 키로 재암호화하는 검증된 도구가 필요하며 env만 바꾸지 않는다. 최초 HTTPS 검증 후 HSTS 확대, preload는 별도 결정. 감사 DB 기록은 운영자 DB 권한으로 변조할 수 있으므로 규제용 변경불가 저장소는 별도 구현한다.

## 회귀 테스트
익명/열람/작성/승인/관리 × 조회/POST/검색/파일/리비전. 문서가 게시 중이고 최신 초안은 비밀인 경우 제목·본문·첨부·export에서 유출 여부 검사. XSS payload, 업로드 경로, 과거 승인본, 본인승인 불허, 오래된 버전 저장, 메뉴 ancestor 비활성, 연결 소유권을 포함한다. 운영 전 OWASP ASVS 수준 및 개인정보 보관 정책을 조직 상황에 맞게 확정한다.

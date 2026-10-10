# 검증 기록

개발환경: Python 3.12 / Django 5.2 계열 / SQLite. PostgreSQL CI는 구성했지만 원격 GitHub 실행 결과는 아직 확인하지 않았다.

## 실행 확인
- Django 전체 테스트: 28개 통과. 공간/노드 권한, 초안 게시 분리, stale write, 정확한 승인 revision, 본인승인, IDOR/첨부, XSS, 메뉴 ancestor 및 연결 정책 포함.
- `ruff check .`: 통과.
- backup/restore shell `bash -n`: 통과. 실제 PostgreSQL backup/restore 실행은 미검증.
- `makemigrations --check --dry-run`: 변경 없음. 초기 및 추가 migration 적용 성공.
- `collectstatic --noinput`: 137개 정적 파일 수집 성공.
- `npm run build`, `npm test`: 블록 편집기/Markdown 전환/체크리스트 및 자동저장 DOM 테스트 2개 통과.
- `npm audit --omit=dev --audit-level=high`: 알려진 취약점 0개. 검사 시점 이후 advisory는 달라질 수 있다.
- Django 개발 서버 실제 구동: `/health/`, `/login/` HTTP 200.
- production bootstrap 환경으로 `check --deploy`: HSTS subdomains/preload 정책 미설정 경고 2개. 하위 도메인의 HTTPS 운영이 미확정되어 자동 활성화하지 않았다.
- DOCX/HTML/ZIP 가져오기 경로/형식/원자성 검사 및 PDF binary 생성 통과. 최신 초안 제목 격리, CSRF, 실제 이미지 검증 및 게시 버전 변경 후 이미지 링크 유지 검증 통과.

## 수정된 보안 경계
게시된 revision에 파일을 직접 추가할 수 있었던 경로를 수정했다. 업로드는 기존 첨부 association을 유지하는 새 초안 revision을 만들고 해당 파일을 새 revision에만 연결한다. 게시본 attachment 집합이 승인 없이 변하지 않는 테스트가 통과한다. 노드 move는 명시 action과 기본 edit action 모두의 inherited deny를 검사한다.

## 검증 제한
Playwright Chromium 실행파일이 없었고 다운로드가 반복적으로 손상되어 브라우저 스크린샷/픽셀 비교를 수행하지 못했다. HTML/template HTTP smoke와 Django tests는 브라우저 렌더링 검증을 대체하지 않는다. 실제 TLS/Nginx/systemd, PostgreSQL 동시성·복원, 접근성 AA, 대량 문서 부하, 외부 API 인증, 운영 로그인 rate-limit/MFA는 운영 전 별도 검증이 필요하다.

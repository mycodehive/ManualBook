# 테스트·릴리스·운영

## 개발 검증
```
uv sync --frozen
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py migrate --noinput
uv run python manage.py bootstrap
uv run python manage.py test
uv run python manage.py collectstatic --noinput
```
`bootstrap`은 기본 메뉴·역할 그룹·사이트 설정만 생성하며 기존 관리자 편집을 덮어쓰지 않아야 한다. 계정 비밀번호는 `createsuperuser`로 별도 생성한다. 실제 command 명칭은 README와 command 파일을 확인한다.

CI는 Python3.12 설치, frozen sync, migration drift, 빈 DB migrate, Django tests. PostgreSQL/MariaDB 선택 DB job에서도 동일한 회귀 테스트를 수행한다. 실제 동시성·잠금 부하 검증은 별도 릴리스 조건이다. 의존성 audit는 별도 GitHub job으로 실행하며 네트워크/advisory availability 실패와 취약점 발견을 구분한다. Playwright는 브라우저 검증 단계의 별도 도입사항이다.

## 배포
기본은 Ubuntu + SQLite + Gunicorn/systemd + Nginx/TLS이며 PostgreSQL/MariaDB는 선택 옵션이다. 자세한 실행은 `docs/operations.md`. `deploy/`는 검토·치환이 필요한 템플릿이며 실제 서버 설치 완료를 뜻하지 않는다. 운영 체크: DEBUG false, 강력한 secret/key, 올바른 hosts/origins, check --deploy, TLS, secure cookies, private media, DB 권한, backup restore.

## 릴리스 절차
1. 사용자에게 유지보수 안내 후 쓰기 요청을 중단하고 worker를 정지한다.
2. DB/첨부의 일관된 snapshot 및 별도 암호화 키 backup. restore 가능 여부 확인.
3. 이전 release/git revision/lock/env 식별 기록.
4. 새 release `uv sync --frozen`, check/test, migrate, collectstatic.
5. systemd 시작; localhost 및 TLS `/health/`, 실제 로그인·게시 문서·비공개 다운로드 검증.
6. 실패 시 서비스 정지. 이전 코드가 새 schema에 호환되면 코드만 되돌릴 수 있다. 아니면 전체 DB/media snapshot을 복원한다. 복원 시 snapshot 이후 쓰기가 사라지므로 승인을 받고 데이터 손실 범위를 알린다.

비가역 migration은 자동 reverse하지 않는다. 백업 없는 운영 migration은 금지한다. 개발 test 결과는 실제 Ubuntu/TLS/성능/접근성 인증을 대체하지 않는다.

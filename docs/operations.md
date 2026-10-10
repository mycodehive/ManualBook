# Ubuntu 운영과 복구

이 문서는 서버에서 운영자가 검토해 실행할 절차다. 실제 서버·도메인·TLS·백업 위치는 아직 확정되지 않았다. 예시는 Ubuntu의 지원 중인 LTS, PostgreSQL, Python3.12, uv, Gunicorn, systemd를 전제로 한다.

## 1. 서버 준비
Ubuntu 보안 업데이트를 적용하고 SSH key 접속을 검증한다. 방화벽은 SSH 관리 IP, 80/443만 허용한다. PostgreSQL/8000은 공개하지 않는다. 제한된 `manualbook` 계정, `/opt/manualbook/releases`, `/var/lib/manualbook/private-media`, `/var/lib/manualbook/static`, `/etc/manualbook`을 만든다. 운영 코드/venv는 배포자가 소유하고 서비스 계정에는 읽기/실행만, private media만 쓰기를 준다. Nginx가 static을 읽을 수 있게 하되 private media 권한은 열지 않는다.

Python3.12·uv는 신뢰할 수 있는 배포 경로로 설치하고 버전을 확인한다. Ubuntu에서 Python venv 및 PDF 런타임은 `python3.12-venv`, `libpango-1.0-0`, `libpangoft2-1.0-0`, `fonts-noto-cjk` 패키지를 설치한다. 선택한 Ubuntu 버전의 Python package 명칭을 확인한다. 배포 release에서 `uv sync --frozen --no-dev`를 실행한다. uv executable은 systemd 시작에 필요하지 않으며 venv의 Gunicorn을 사용한다.

## 2. PostgreSQL
로컬 또는 private network DB를 사용한다. DBA 계정으로 최소권한 사용자와 DB를 생성한다. 비밀번호는 `psql`의 `\password manualbook` 같은 대화형 방법으로 설정하고 셸 기록에 입력하지 않는다.

```sql
CREATE ROLE manualbook LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE manualbook OWNER manualbook;
```

서버 pg_hba는 허용된 앱 연결만 scram-sha-256 등 조직 정책으로 제한한다. 최초 migration 계정과 런타임 계정을 분리하려면 schema DDL privileges·sequence grants를 검토한다. 운영 백업용 `.pg_service.conf`/`.pgpass`는 권한 0600으로 보호한다.

## 3. 환경파일
`/etc/manualbook/manualbook.env`를 root:manualbook 0640으로 생성한다. key는 임의 placeholder를 복사하지 않고 별도 생성한다.

```dotenv
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<독립적으로 생성한 50자 이상 무작위 값>
INTEGRATION_ENCRYPTION_KEY=<Fernet.generate_key() 결과>
DATABASE_URL=postgresql://manualbook:<URL-escaped-password>@127.0.0.1:5432/manualbook
DJANGO_ALLOWED_HOSTS=manualbook.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://manualbook.example.com
DJANGO_TRUST_PROXY=true
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SECURE_HSTS_SECONDS=0
DJANGO_STATIC_ROOT=/var/lib/manualbook/static
DJANGO_MEDIA_ROOT=/var/lib/manualbook/private-media
```

환경변수는 서비스 환경에서 전달한다. `.env` 프로젝트 파일을 사용하는 경우 파일 권한과 백업 포함 여부를 검토하고 커밋하지 않는다. env values를 로그/CI에 출력하지 않는다. 키 백업은 DB와 별도 암호화된 저장소에 둔다.

## 4. 설치 명령
환경이 적용된 shell에서 release 경로에서 실행한다. 운영 설정은 HTTPS redirect 때문에 localhost `/health/` 호출도 `X-Forwarded-Proto: https`와 허용 Host가 필요하다.

```
uv run python manage.py check --deploy
uv run python manage.py migrate --noinput
uv run python manage.py bootstrap
uv run python manage.py createsuperuser
uv run python manage.py collectstatic --noinput
```

`deploy/manualbook.service`의 경로/worker 수를 서버 자원에 맞춰 검토하여 설치한다. systemd unit의 `ProtectSystem=strict`를 유지하고 private media 이외 임의 쓰기를 허용하지 않는다. `systemctl daemon-reload`, `enable --now manualbook`, `journalctl -u manualbook`로 확인한다.

Nginx 템플릿의 도메인·인증서 경로를 실제 값으로 바꾸고 인증서 발급을 완료한 후 `nginx -t` 및 reload. 처음 인증서 발급에는 별도 HTTP ACME challenge 구성이 필요하다. `/media/` 및 `/private-media/`는 공개하지 않는다. Cloud/Proxy 사용 시 `DJANGO_TRUST_PROXY`는 오직 직접 연결된 프록시가 전달 헤더를 덮어쓰는 경우에만 켠다.

## 5. 운영 전 확인
- `check --deploy` 경고를 설명/처리하고 DEBUG false, hosts/origins, cookie, HTTPS를 확인.
- HTTPS 로그인과 로그아웃, 그룹별 메뉴/direct URL, 초안 격리, 권한 있는 첨부 다운로드를 실제 브라우저에서 확인.
- `.env`, sqlite, private media, git 파일이 HTTP에서 열리지 않는지 확인.
- 정책에 맞게 HSTS를 단계적으로 늘린다. preload/includeSubDomains는 하위 사이트까지 검토 후 결정.
- proxy rate-limit 또는 IdP MFA, 관리자 계정 복구, 로그 보관·모니터링·저장공간 알림을 설정.
- `/health/`는 프로세스 응답 확인용이며 모든 통합·스토리지·보안의 정상 상태 보증이 아니다.

## 6. 백업과 복원
`scripts/backup.sh`는 쓰기 중지 유지보수 창에서 DB와 private media를 같이 저장한다. live DB dump와 동시에 변하는 파일을 조합하면 일관성이 보장되지 않는다. 백업은 권한 0700/0600, 암호화 후 off-host, 날짜별 보존 및 무결성 검증. 정책 예시 매일/30일은 제안이고 RPO/RTO를 실제 조직에서 정한다.

복구 훈련은 새 빈 PostgreSQL DB·빈 private media directory에 `scripts/restore_verify.sh /absolute/snapshot-path`. 해당 DB를 가리키는 DATABASE_URL, 같은 암호화 키와 backup 당시 코드 revision으로 앱 검사·게시 문서·파일·연결 복호화를 검증한다. 스크립트의 PGSERVICE는 반드시 훈련 DB를 가리킨다.

실제 장애 복구: maintenance → 서비스 정지 → 기존 상태 별도 backup → 검증된 DB/media snapshot restore → matching key/env/code → check/migrate가 필요한지 검토 → 서비스 시작 → 권한/게시/파일 smoke → 트래픽 재개. snapshot 이후 작성 내용이 없어지는 복구는 사용자에게 손실 구간을 알린다.

## 7. 업데이트와 롤백
새 release directory에서 frozen dependencies 준비, 운영과 동일 설정으로 checks/test, 쓰기 중지, DB/media backup, migration, static, current link 전환, 재시작·smoke. 이전 schema에 대한 코드 호환이 확인되면 이전 release로 code rollback 가능. 비가역 schema 변화는 DB restore가 필요하며 이후 쓰기 손실 가능. `migrate <old>`를 무조건 실행하지 않는다. 배포별 git revision·migration·backup 위치를 기록한다.

## 8. 키 회전
새 Fernet key를 env에 교체만 하면 기존 secret을 복호화할 수 없다. 앱에 검증된 rotation management command가 없으면 기존 key를 유지한다. 도구 추가 후 maintenance, old key backup, 전체 복호화 검증, transaction 내 재암호화, new key로 전체 검증, 실패 시 DB+old key 복원 순서를 적용한다.

## 가져오기·PDF 제한
가져오기는 10MB 업로드, ZIP 최대 100항목/해제20MB/압축률100배/폴더20단계, Markdown/HTML/DOCX만 지원한다. PDF는 외부/로컬 URL fetch를 금지하고 이미지를 제외한다. DOCX 복잡한 레이아웃·각주·이미지를 그대로 재현하지 않는다. 중첩 DOCX를 포함한 총 해제량도 20MB로 제한한다. PDF 렌더링 시간/메모리 예산은 운영 부하검증 후 격리 worker로 강화한다.

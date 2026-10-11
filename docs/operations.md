# Ubuntu 운영과 복구

이 문서는 서버에서 운영자가 검토해 실행할 절차다. 실제 서버·도메인·TLS·백업 위치는 아직 확정되지 않았다. 기본은 Ubuntu의 지원 중인 LTS, SQLite, Python3.12, uv, Gunicorn, systemd다. PostgreSQL과 MariaDB는 선택한다.

## 1. 서버 준비
Ubuntu 보안 업데이트를 적용하고 SSH key 접속을 검증한다. 방화벽은 SSH 관리 IP, 80/443만 허용한다. 선택 DB 서버의 포트와 8000은 공개하지 않는다. 제한된 `manualbook` 계정, `/opt/manualbook/releases`, `/var/lib/manualbook/private-media`, `/var/lib/manualbook/static`, `/etc/manualbook`을 만든다. 운영 코드/venv는 배포자가 소유하고 서비스 계정에는 읽기/실행만, SQLite DB 디렉터리와 private media만 쓰기를 준다. Nginx가 static을 읽을 수 있게 하되 private media 권한은 열지 않는다.

Python3.12·uv는 신뢰할 수 있는 배포 경로로 설치하고 버전을 확인한다. Ubuntu에서 Python venv 및 PDF 런타임은 `python3.12-venv`, `libpango-1.0-0`, `libpangoft2-1.0-0`, `fonts-noto-cjk` 패키지를 설치한다. 선택한 Ubuntu 버전의 Python package 명칭을 확인한다. 배포 release에서 `uv sync --frozen --no-dev`를 실행한다. uv executable은 systemd 시작에 필요하지 않으며 venv의 Gunicorn을 사용한다.

## 2. DB 선택
### SQLite (기본)
별도 DB 서버가 필요 없다. `/var/lib/manualbook`을 서비스 계정이 쓸 수 있게 만들고 디렉터리 0700, DB 파일 0600 권한을 적용한다. 저널/WAL/SHM 생성에도 부모 디렉터리 쓰기권한이 필요하다. 운영 DB를 release 코드 폴더에 두지 않는다.

`DATABASE_URL=sqlite:////var/lib/manualbook/db.sqlite3`와 기본 `uv sync --frozen --no-dev`를 사용한다. SQLite는 쓰기 트랜잭션 IMMEDIATE, 기본 잠금 대기 20초로 구성한다. systemd 기본 worker는 1개이며 다중 동시 쓰기 규모는 실제 부하 검증으로 결정한다.

### PostgreSQL (선택)
`uv sync --frozen --no-dev --extra postgres`, `DATABASE_URL=postgresql://USER:URL_ENCODED_PASSWORD@HOST:5432/DB`를 설정한다. 로컬 DB를 사용하면 systemd의 `After=`에 해당 DB 서비스를 선택적으로 추가한다.

로컬 또는 private network DB를 사용한다. DBA 계정으로 최소권한 사용자와 DB를 생성한다. 비밀번호는 `psql`의 `\password manualbook` 같은 대화형 방법으로 설정하고 셸 기록에 입력하지 않는다.

```sql
CREATE ROLE manualbook LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE manualbook OWNER manualbook;
```

서버 pg_hba는 허용된 앱 연결만 scram-sha-256 등 조직 정책으로 제한한다. 최초 migration 계정과 런타임 계정을 분리하려면 schema DDL privileges·sequence grants를 검토한다. 운영 백업용 `.pg_service.conf`/`.pgpass`는 권한 0600으로 보호한다.

### MariaDB (선택)
Django 5.2 지원 MariaDB를 사용한다(CI: 11.4). Ubuntu 드라이버 빌드 준비: `sudo apt-get install python3-dev default-libmysqlclient-dev build-essential pkg-config`. 설치는 `uv sync --frozen --no-dev --extra mariadb`, 연결은 `DATABASE_URL=mysql://USER:URL_ENCODED_PASSWORD@HOST:3306/DB`다. 전용 최소권한 계정을 만들고 InnoDB를 사용한다. DB 생성 예:

```sql
CREATE DATABASE manualbook CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
```

비밀번호는 보호된 DBA/client 설정에서 관리하고 명령행 인수에 넣지 않는다. 설정은 utf8mb4, STRICT_TRANS_TABLES, read committed를 적용한다. `utf8mb4_bin`은 SQLite와 동일한 대소문자 구별을 유지하기 위한 선택이다. 기존 DB의 대소문자 중복·FK·JSON/UUID를 이관 전에 검증한다. MariaDB DDL은 실패 시 부분 적용될 수 있으므로 스테이징에서 마이그레이션과 백업 복구를 먼저 확인한다.

## 3. 환경파일
`/etc/manualbook/manualbook.env`를 root:manualbook 0640으로 생성한다. key는 임의 placeholder를 복사하지 않고 별도 생성한다.

```dotenv
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<독립적으로 생성한 50자 이상 무작위 값>
INTEGRATION_ENCRYPTION_KEY=<Fernet.generate_key() 결과>
DATABASE_URL=sqlite:////var/lib/manualbook/db.sqlite3
DJANGO_ALLOWED_HOSTS=manualbook.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://manualbook.example.com
DJANGO_TRUST_PROXY=true
DJANGO_TRUSTED_PROXY_IPS=127.0.0.1,::1
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

선택 DB를 사용할 때 위 `uv run` 명령에 `--extra postgres` 또는 `--extra mariadb`를 추가한다. 서비스 실행은 이미 설치된 venv의 Gunicorn을 직접 사용한다.

`deploy/manualbook.service`의 경로/worker 수를 서버 자원에 맞춰 검토하여 설치한다. systemd unit의 `ProtectSystem=strict`를 유지하고 SQLite DB 및 private media의 `/var/lib/manualbook` 이외 임의 쓰기를 허용하지 않는다. `systemctl daemon-reload`, `enable --now manualbook`, `journalctl -u manualbook`로 확인한다.

Nginx 템플릿의 도메인·인증서 경로를 실제 값으로 바꾸고 인증서 발급을 완료한 후 `nginx -t` 및 reload. 처음 인증서 발급에는 별도 HTTP ACME challenge 구성이 필요하다. `/media/` 및 `/private-media/`는 공개하지 않는다. Cloud/Proxy 사용 시 `DJANGO_TRUST_PROXY`는 오직 직접 연결된 프록시가 전달 헤더를 덮어쓰는 경우에만 켠다.

## 5. 운영 전 확인
- `check --deploy` 경고를 설명/처리하고 DEBUG false, hosts/origins, cookie, HTTPS를 확인.
- 최고 관리자로 조직과 첫 관리자 등록; 서로 다른 조직의 문서·검색·첨부 ID 직접 접근이 거부되는지 확인.
- `/o/<slug>/login/` HTTPS 로그인과 로그아웃, 그룹별 메뉴/direct URL, 초안 격리, 권한 있는 첨부 다운로드를 실제 브라우저에서 확인.
- `.env`, sqlite, private media, git 파일이 HTTP에서 열리지 않는지 확인.
- 정책에 맞게 HSTS를 단계적으로 늘린다. preload/includeSubDomains는 하위 사이트까지 검토 후 결정.
- proxy rate-limit 또는 IdP MFA, 관리자 계정 복구, 로그 보관·모니터링·저장공간 알림을 설정.
- `/health/`는 프로세스 응답 확인용이며 모든 통합·스토리지·보안의 정상 상태 보증이 아니다.

## 6. 백업과 복원
`scripts/backup.sh`는 쓰기 중지 유지보수 창에서 DB와 private media를 같이 저장한다. live DB dump와 동시에 변하는 파일을 조합하면 일관성이 보장되지 않는다. 백업은 권한 0700/0600, 암호화 후 off-host, 날짜별 보존 및 무결성 검증. 정책 예시 매일/30일은 제안이고 RPO/RTO를 실제 조직에서 정한다.

백업 스크립트는 기본 `MANUALBOOK_DB_ENGINE=sqlite`다. 다음 환경을 설정하고 `scripts/backup.sh`를 실행한다.

```bash
export MANUALBOOK_SQLITE_PATH=/var/lib/manualbook/db.sqlite3
export MANUALBOOK_MEDIA_ROOT=/var/lib/manualbook/private-media
export MANUALBOOK_BACKUP_ROOT=/protected/manualbook-backups
```

SQLite는 표준 Python sqlite3 backup API로 snapshot을 만들며 활성 DB 파일을 단순 복사하지 않는다. 복구 훈련에는 `MANUALBOOK_SQLITE_PATH`를 아직 존재하지 않는 별도 절대경로로, `MANUALBOOK_RESTORE_MEDIA_ROOT`를 빈 디렉터리로 지정한다. 기존 파일은 덮어쓰지 않고 integrity/FK 검사를 수행한다.

PostgreSQL 옵션은 `MANUALBOOK_DB_ENGINE=postgres` 및 보호된 `.pg_service.conf`/`.pgpass`의 `PGSERVICE`를 사용한다. MariaDB 옵션은 `MANUALBOOK_DB_ENGINE=mariadb`, `MANUALBOOK_DB_CLIENT_FILE`(0600 client option file), `MANUALBOOK_DB_NAME`을 사용한다. 복구 시에는 반드시 별도 훈련 DB에 연결하는 client 파일을 지정한다. MariaDB dump는 InnoDB·DDL 없는 쓰기 중지 창에서 생성한다. Snapshot에는 엔진과 체크섬이 기록되며 엔진이 다른 복구는 거부한다. DBURL 변경이나 백업 복원은 엔진 간 이관을 수행하지 않는다.

복구 훈련은 새 빈 선택 DB·빈 private media directory에 `scripts/restore_verify.sh /absolute/snapshot-path`. 해당 DB를 가리키는 DATABASE_URL, 같은 암호화 키와 backup 당시 코드 revision으로 앱 검사·게시 문서·파일·연결 복호화를 검증한다. DB 경로/PGSERVICE/MariaDB client 파일은 반드시 훈련 DB를 가리킨다.

실제 장애 복구: maintenance → 서비스 정지 → 기존 상태 별도 backup → 검증된 DB/media snapshot restore → matching key/env/code → check/migrate가 필요한지 검토 → 서비스 시작 → 권한/게시/파일 smoke → 트래픽 재개. snapshot 이후 작성 내용이 없어지는 복구는 사용자에게 손실 구간을 알린다.

## 7. 업데이트와 롤백
새 release directory에서 frozen dependencies 준비, 운영과 동일 설정으로 checks/test, 쓰기 중지, DB/media backup, migration, static, current link 전환, 재시작·smoke. 이전 schema에 대한 코드 호환이 확인되면 이전 release로 code rollback 가능. 비가역 schema 변화는 DB restore가 필요하며 이후 쓰기 손실 가능. `migrate <old>`를 무조건 실행하지 않는다. 배포별 git revision·migration·backup 위치를 기록한다.

## 8. 키 회전
새 Fernet key를 env에 교체만 하면 기존 secret을 복호화할 수 없다. 앱에 검증된 rotation management command가 없으면 기존 key를 유지한다. 도구 추가 후 maintenance, old key backup, 전체 복호화 검증, transaction 내 재암호화, new key로 전체 검증, 실패 시 DB+old key 복원 순서를 적용한다.

## 가져오기·PDF 제한
가져오기는 10MB 업로드, ZIP 최대 100항목/해제20MB/압축률100배/폴더20단계, Markdown/HTML/DOCX만 지원한다. PDF는 외부/로컬 URL fetch를 금지하고 이미지를 제외한다. DOCX 복잡한 레이아웃·각주·이미지를 그대로 재현하지 않는다. 중첩 DOCX를 포함한 총 해제량도 20MB로 제한한다. PDF 렌더링 시간/메모리 예산은 운영 부하검증 후 격리 worker로 강화한다.

## 조직 이관 및 로그인 제한
단일 조직 버전에서 업데이트하면 기존 데이터와 계정·그룹은 legacy 조직에 귀속됩니다. 쓰기를 중지하고 DB와 private media를 함께 백업한 후 migrate를 실행하고 /o/legacy/login/에서 기존 계정으로 동작을 검증합니다.
로그인 실패 제한은 조직/아이디·조직/접속 IP의 해시 키를 DB에 저장합니다. 운영자는 주기적으로 24시간 이상 지난 LoginThrottle 레코드를 삭제할 수 있습니다. 글로벌 관리자 잠금이 발생하면 15분 대기 또는 신뢰된 운영 콘솔에서 해당 레코드를 정리합니다. 직접 연결된 nginx의 소켓 IP를 DJANGO_TRUSTED_PROXY_IPS에 지정하면 nginx가 덮어쓴 X-Real-IP를 검증해 사용합니다. 다른 소켓에서 보내는 헤더는 무시합니다. 프록시 IP를 정확히 설정하지 않으면 공유 프록시 주소의 한도가 적용됩니다. X-Forwarded-For는 임의로 신뢰하지 않습니다.

## 로그아웃 CSRF 403 진단

로그아웃은 POST와 CSRF 검증을 유지합니다. 다른 탭에서 로그인하면서 CSRF 쿠키가 회전한 경우 제출 직전에 현재 쿠키의 토큰으로 갱신합니다. 검증 실패 시 로그인 세션은 유지되고 새 토큰을 가진 명시적인 재시도 폼을 표시합니다. GET 요청은 로그아웃하지 않습니다.

반복되는 실패는 서버의 `django.security.csrf` 로그로 구분하세요. 실제 서버의 서비스 이름으로 아래 명령을 바꿉니다.

```bash
sudo journalctl -u manualbook -n 100 --no-pager
```

- `CSRF cookie not set`: 운영 환경은 Secure 쿠키를 사용하므로 HTTPS로 접속하고 브라우저 쿠키 허용 여부를 확인합니다.
- `CSRF token ... incorrect`: 페이지 새로고침 또는 로그아웃 재시도 폼을 사용합니다.
- `Origin checking failed` / `Referer checking failed`: 접속 주소의 스킴·호스트·포트를 확인합니다. Nginx가 TLS를 종료한다면 `DJANGO_TRUST_PROXY=true`와 `X-Forwarded-Proto` 전달이 필요하며 Gunicorn은 신뢰하는 프록시 뒤에 배치합니다. 이 설정은 외부에서 임의 전달한 프록시 헤더를 신뢰하는 용도로 사용하면 안 됩니다.

필요한 trusted origin은 `.env`의 `DJANGO_CSRF_TRUSTED_ORIGINS`에 실제 접속 주소만 입력합니다. 예: `https://manualbook.example.com` 또는 외부 포트를 쓴다면 `https://manualbook.example.com:36980`. `DJANGO_ALLOWED_HOSTS`에는 스킴과 포트 없이 호스트 이름을 입력합니다. 다른 사이트를 광범위하게 신뢰하도록 지정하거나 CSRF 검증을 끄지 않습니다.

Nginx 예제는 `Host $http_host`로 외부 포트를 보존합니다. 기존 서버에서 적용할 때는 해당 프록시 설정과 환경변수를 확인하고 `sudo nginx -t` 후 Nginx를 reload하고 Django 서비스를 재시작하세요. 정확한 운영 원인은 실패 로그 없이 확정할 수 없습니다.

## 전역 로그인 및 사용자 아이디 정책

사이트 루트(`/`)와 `/login/`에서 조직 구성원도 로그인할 수 있습니다. 조직 로그인(`/o/<조직>/login/`)에서도 같은 로그인 아이디를 사용합니다. 구성원은 활성 조직과 활성 멤버십이 있어야 로그인할 수 있으며, 조직 로그인은 해당 조직 가입 여부를 검사합니다. 소속 조직이 하나면 해당 조직으로, 여러 개면 조직 선택 화면으로 이동합니다. 최고관리자는 전체 조직 선택 화면으로 이동하고 각 활성 조직에도 접속할 수 있습니다.

사용자 아이디는 전체 조직에서 영문 대소문자를 구분하지 않고 중복을 금지합니다. 사용자 생성 폼과 공통 생성 서비스, Django 관리자 사용자 생성에서 같은 정책을 검사합니다. `/organizations/identity-policy/`는 사이트 최고관리자만 수정할 수 있으며 전체 조직 관리 화면의 ‘아이디 정책’ 버튼으로 접근합니다. 기본 금지 목록은 admin, administrator, admins, manager, superadmin, root, superuser, sysadmin이며 최고관리자가 한곳에서 추가·삭제합니다. 기존 계정은 금지 목록에 추가해도 로그인이 유지됩니다. 최고관리자 계정 생성은 예약 아이디 예외이며 중복 검사에는 예외가 없습니다.

업데이트 시 DB를 백업한 뒤 `uv run --frozen python manage.py migrate`를 실행합니다. 기존 `org번호__아이디` 계정은 공개 로그인 아이디에 연결하며 사용자 번호, 비밀번호, 문서 및 권한 연결을 변경하지 않습니다. 기존 짧은 아이디가 조직 간에 충돌하면 해당 계정은 원래의 전체 내부 아이디를 고유 로그인 아이디로 유지합니다. 계정을 합치거나 삭제하지 않습니다. 아래 명령으로 실제 로그인 아이디를 확인해 사용자에게 안내하세요.

```bash
uv run --frozen python manage.py list_login_identities
```

기존 전체 아이디 자체가 대소문자만 다르게 중복된 경우에는 마이그레이션이 명확한 오류로 중단됩니다. 해당 계정의 새 고유 아이디를 결정한 뒤 업그레이드 전에 정리해야 하며 임의로 계정을 합치지 않습니다. 로그인 제한은 같은 전역 아이디에 대해 조직·전역 로그인 주소를 바꿔도 적용됩니다.

## 로그인 계정 전환과 최고관리자 이동

최고관리자는 조직 로그인 주소나 `next` 값과 관계없이 `/organizations/`로 이동한 뒤 관리할 조직을 명시적으로 선택합니다. 일반 사용자는 실제 인증된 사용자의 활성 소속 조직을 기준으로 이동하고, 소속되지 않은 조직의 로그인 및 보호 화면 접근은 거부됩니다.

기존 계정으로 로그인된 상태에서도 로그인 폼을 열고 다른 계정으로 전환할 수 있습니다. 이전 세션의 조직 권한으로 새 로그인 폼을 막지 않으며, 새 로그인 성공 시 Django가 이전 계정의 세션을 폐기하고 새 계정 세션과 CSRF 토큰을 설정합니다. 비밀번호가 틀리면 기존 로그인 상태를 유지합니다. 로그인 화면과 인증된 전역 화면은 `private, no-store`와 `Vary: Cookie`를 적용합니다. 테마·메뉴 펼침 상태는 사용자 신원과 분리되어 있으며 저장된 테마를 지울 필요는 없습니다.

## 매뉴얼 공간 공개 범위

공간 설정의 ‘공개 범위’에서 ‘공개’ 또는 ‘비공개’를 선택합니다. 기본값은 비공개이며 기존 공간도 비공개 상태를 유지합니다. 공개 공간은 해당 조직의 공간 주소를 공유하면 로그인 없이 게시 문서를 읽을 수 있습니다. 공간의 공개 설정은 조직 전체나 다른 공간을 공개하지 않습니다.

공개 방문자 화면에는 게시 문서와 게시본에 연결된 첨부파일만 표시합니다. 공간 목록, 조직 메뉴, 초안, 문서 편집·생성, 휴지통, 공간 설정, 즐겨찾기, 문서 가져오기·내보내기 기능은 표시하지 않습니다. 기존 조직 구성원과 관리자는 로그인 후 원래 권한에 따라 관리 기능을 사용합니다. 공개 범위 변경 전에 게시 문서와 첨부파일에 외부 공개할 수 없는 정보가 없는지 확인하세요. 비공개로 되돌리면 새 공개 요청에는 기존 조직 접근 권한이 필요하며 이미 내려받은 자료는 회수되지 않습니다.

## 소개 페이지

`/intro`와 `/intro/`는 로그인 없이 업로드된 소개 페이지를 표시합니다. HTML은 `templates/core/intro.html`, 이미지는 `static/intro/images/`에 있습니다. 조직별 주소와 기존 로그인 이동은 그대로 적용됩니다.

운영 반영 시 코드를 업데이트한 다음 `uv run --frozen python manage.py collectstatic --noinput`을 실행하고 웹 애플리케이션 서비스를 재시작합니다. DB 마이그레이션은 필요하지 않습니다. 기존 `manualbook.writeaday.click` 도메인과 정적 파일 제공 설정을 사용합니다.

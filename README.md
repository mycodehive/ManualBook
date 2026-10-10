# ManualBook

독립형 GitBook 스타일 사내 매뉴얼 플랫폼. `mycodehive/iacfgeneral_ver3`의 Enterprise Platform 공통 UI/UX·환경설정·모듈 구조를 적용하며 기존 업무 데이터와 비밀은 가져오지 않습니다. 여러 조직이 고유 슬러그 아래에서 독립적으로 사용하는 로컬 계정 기반 플랫폼입니다.

## 실행
Python 3.12 및 uv로 관리합니다. `.venv` 생성·의존성 설치·실행을 uv로 처리하며, 자세한 작업 흐름은 [uv 프로젝트 관리](docs/uv.md)를 참고하세요.

```bash
cp .env.example .env
uv sync --frozen
```

`.env`의 개발 설정을 확인하고 `INTEGRATION_ENCRYPTION_KEY`를 독립적으로 생성해 입력합니다.

```bash
uv run --frozen python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
uv run --frozen python manage.py migrate
uv run --frozen python manage.py bootstrap
uv run --frozen python manage.py createsuperuser
uv run --frozen python manage.py runserver
```

사이트 최고 관리자 로그인: `http://127.0.0.1:8000/login/` (실제 URL은 `config/urls.py`). 기본 계정/비밀번호는 제공하지 않습니다. 기본 DB는 SQLite입니다. PostgreSQL과 MariaDB는 선택 옵션이며, 운영에는 HTTPS·강력한 secret·암호화 키가 필요합니다. PDF에는 Ubuntu `libpango-1.0-0`, `libpangoft2-1.0-0`와 `fonts-noto-cjk`가 필요합니다.

## DB 선택
`DATABASE_URL`이 비어 있거나 없으면 프로젝트 폴더의 `db.sqlite3`를 사용합니다. SQLite는 별도 DB 서버나 드라이버 설치가 필요하지 않습니다. 상대 SQLite 경로도 프로젝트 폴더를 기준으로 처리합니다.

| DB | 설치 | `.env` 설정 예시 |
|---|---|---|
| SQLite (기본) | `uv sync --frozen` | `DATABASE_URL=` |
| PostgreSQL (선택) | `uv sync --frozen --extra postgres` | `DATABASE_URL=postgresql://USER:URL_ENCODED_PASSWORD@HOST:5432/DB` |
| MariaDB (선택) | `uv sync --frozen --extra mariadb` | `DATABASE_URL=mysql://USER:URL_ENCODED_PASSWORD@HOST:3306/DB` |

선택 DB로 실행할 때 `uv run --frozen --extra postgres ...` 또는 `uv run --frozen --extra mariadb ...`를 사용하세요. 예: `uv run --frozen --extra mariadb python manage.py migrate`. 일반 `uv run --frozen`은 선택 드라이버를 제거할 수 있습니다. MariaDB는 Django MySQL 백엔드와 `mysqlclient`를 사용하며 `mariadb://` 별칭도 허용합니다. Ubuntu의 MariaDB 드라이버 빌드에는 `python3-dev default-libmysqlclient-dev build-essential pkg-config`가 필요할 수 있습니다.

SQLite 운영 경로는 release 코드 밖의 `DATABASE_URL=sqlite:////var/lib/manualbook/db.sqlite3`를 권장합니다. 서비스 계정에 부모 디렉터리 쓰기권한도 부여하세요. 기본 서비스는 worker 1개이며 SQLite 쓰기 트랜잭션은 IMMEDIATE, 잠금 대기 기본값은 20초입니다. PostgreSQL/MariaDB를 선택한 경우 worker 수는 부하 검증 후 조정하세요.

DB 선택을 바꾸면 해당 DB에 연결하며 기존 데이터를 자동 복사하지 않습니다. 기존 데이터가 있으면 DB·첨부·암호화 키를 백업하고 별도 이관·복구 검증을 수행하세요. 상세 절차는 [운영 문서](docs/operations.md)를 참고하세요.

## 구현 범위
- 참조 공통 셸, 상단/좌측 3단 동적 메뉴, 라이트/다크, 조직 브랜딩.
- 최고 관리자 조직 등록·첫 관리자 생성; 조직별 관리자·사용자·부서·그룹 등록, 독립 메뉴·브랜딩·감사 기록;
- 조직별 연결 관리; 연결 비밀 암호화, 리소스·기능 바인딩과 설정 이력.
- 공간 그룹 권한, 문서/폴더 트리, 이동·복사·정렬·보관·휴지통/복구.
- 로컬 Tiptap 블록 편집과 Markdown 모드, 안전한 HTML 정제, 자동저장·낙관적 충돌 검사.
- 불변 revision, 정확한 revision 검토·승인·반려·게시, 본인 승인 정책, diff·복원.
- 게시본 검색, 즐겨찾기, 비공개 첨부, Markdown/HTML/DOCX/ZIP import, Markdown/PDF export 및 허용 문서의 Space ZIP export.
- 노드별 사용자/그룹 allow/deny와 조상 deny 우선 정책 및 전용 ACL 관리 UI.

외부 연결 '테스트'는 설정 검증입니다. 실제 제공자 API 연결·인증 성공으로 간주하지 않습니다. block editor는 Markdown으로 저장하므로 복잡한 서식을 완전히 보존하지 않습니다. 실제 문서에 맞춰 편집/게시 결과를 확인하세요. DOCX는 기본 문단/표만 변환하며 PDF는 보안상 이미지와 외부 리소스를 가져오지 않습니다.

## 개발 검증
```bash
uv run --frozen ruff check .
uv run --frozen python manage.py check
uv run --frozen python manage.py makemigrations --check --dry-run
uv run --frozen python manage.py test
uv run --frozen python manage.py collectstatic --noinput
```

편집기 JS 수정 시 Node.js 환경에서 `npm ci` 및 `npm run build`로 로컬 번들을 재생성합니다. `npm test`로 편집기·자동저장 DOM 회귀 검사를 실행합니다. 일반 Python 실행에는 저장소의 빌드된 번들을 사용합니다. CI는 SQLite/PostgreSQL/MariaDB 테스트 및 의존성 audit를 실행합니다. 검증 결과와 제한 사항은 [검증 기록](docs/verification.md)을 참조하세요.

## 조직 운영

최고 관리자는 `/organizations/`에서 조직과 첫 관리자를 등록합니다. 조직의 고유 주소는 `/o/<slug>/`이며 주소 식별자는 생성 후 변경할 수 없습니다. 조직 관리자·사용자는 `/o/<slug>/login/`에서 짧은 아이디로 로그인합니다. 같은 아이디를 여러 조직에서 사용할 수 있고, 전역 관리자 권한은 최고 관리자에게만 부여합니다. 조직의 `/organization/members/`, `/organization/departments/`, `/organization/groups/`에서 구성원을 관리합니다. 조직 비활성화나 구성원 비활성화는 다음 요청부터 접근을 차단합니다. 마지막 활성 조직 관리자의 해제는 차단합니다.

로그인 실패는 조직·아이디별 5회 및 조직·접속 IP별 20회에 도달하면 15분간 제한합니다. DB 기반이므로 여러 앱 worker에 적용됩니다.

기존 데이터는 마이그레이션으로 `legacy` 조직에 귀속됩니다. 기존 사용자·그룹·매뉴얼·설정·연결·감사 기록을 유지하며 기존 아이디로 `legacy` 조직에서 로그인할 수 있습니다. 이관 전에 DB와 private media를 함께 백업하세요. 새 조직의 메뉴·그룹은 조직 등록 시 생성됩니다. `bootstrap`은 조직별 기본값을 확인하며 운영자가 변경한 값을 덮어쓰지 않습니다.

조직 범위가 없는 기본 ORM 조회는 빈 결과를 반환하고 저장은 거부합니다. 매뉴얼·revision·첨부·승인·메뉴·연결·환경설정·감사 로그를 조직별로 조회하며 FK·그룹 연결의 조직 일치를 검증합니다. 최고 관리자도 선택한 조직 안에서 문서를 관리합니다. 권한 확인 전 다른 조직의 연결 객체를 노출하지 않습니다. 상세 내용은 [조직 격리 설계](docs/tenancy.md)를 참조하세요.

## 남은 운영/제품 작업
고급 블록 서식·Mermaid, 댓글, 한국어 형태소/FTS 품질검증, SSO/MFA, AI/RAG, E2E/접근성/부하 검증은 후속입니다. production-ready 또는 전체 v1 계획 완료로 간주하지 않습니다. 실제 브라우저 스크린샷 비교는 실행환경에서 Chromium 설치가 막혀 완료되지 않았습니다.

## 문서
- [개발 계획](docs/planning/01_product_requirements.md) 및 `docs/planning/`의 8개 명세
- [Ubuntu 설치·운영·백업·복원](docs/operations.md)
- [플랫폼 커스터마이징](CUSTOM.md)
- `deploy/manualbook.service`, `deploy/nginx.conf`: 치환·검토가 필요한 운영 템플릿
- `scripts/backup.sh`, `scripts/restore_verify.sh`: 유지보수 백업 및 빈 DB/디렉터리 복구 훈련

배포 서버에 설치한 상태가 아닙니다. 운영 진입 전에 백업 복구 훈련, 선택한 DB의 동시성, TLS/private media 및 권한 smoke를 검증하세요. 원본 UI 자산과 의존성의 배포 라이선스를 외부 배포 전에 확인해야 합니다.

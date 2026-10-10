# uv 프로젝트 관리

ManualBook는 uv가 관리하는 Django 애플리케이션이다. 의존성은 `pyproject.toml`, 확정 버전은 `uv.lock`, 기본 Python은 `.python-version`의 3.12로 관리한다. `uv sync`가 프로젝트의 `.venv`를 생성하고 설치한다. 개발 도구는 기본 `dev` 그룹, DB 드라이버는 선택 extra로 분리한다.

## 처음 설치

uv를 설치한 뒤 프로젝트 폴더에서 실행한다. uv 설치 방법: https://docs.astral.sh/uv/getting-started/installation/

```bash
uv python install 3.12
uv sync --frozen
```

`.env.example`을 `.env`로 복사하고 README의 암호화 키·환경설정을 완료한다. Windows PowerShell에서는 `Copy-Item .env.example .env`, macOS/Linux에서는 `cp .env.example .env`를 사용한다. 기존 `.env`가 있다면 다시 복사해 덮어쓰지 않는다.

```bash
uv run --frozen python manage.py migrate
uv run --frozen python manage.py bootstrap
uv run --frozen python manage.py createsuperuser
uv run --frozen python manage.py runserver
```

별도 가상환경 활성화 없이 `uv run`이 `.venv`의 Python을 사용한다. SQLite가 기본 DB다. PostgreSQL/MariaDB 선택 설치와 실행:

```bash
uv sync --frozen --extra postgres
uv run --frozen --extra postgres python manage.py migrate

uv sync --frozen --extra mariadb
uv run --frozen --extra mariadb python manage.py migrate
```

위 두 DB 설정은 대안이며, `.env`의 `DATABASE_URL`은 선택한 DB에 맞춘다. MariaDB의 시스템 빌드 의존성과 PDF 시스템 라이브러리는 README 및 운영 문서를 참고한다. uv는 Python 의존성을 관리하며 DB 서버·시스템 라이브러리는 별도 설치한다.

## 의존성 변경

```bash
uv add 패키지명
uv add --group dev 개발도구명
uv remove 패키지명
uv lock --upgrade-package 패키지명
uv sync --frozen
```

변경 후 `pyproject.toml`과 `uv.lock`을 함께 커밋한다. `.venv`는 커밋하지 않는다. 일반 설치·배포에는 `--frozen`을 사용하고 버전 변경은 의도한 의존성 작업에서만 수행한다. 메타데이터를 직접 수정했다면 `uv lock`으로 잠금 파일을 갱신한다.

## 검증과 운영 설치

```bash
uv lock --check
uv run --frozen ruff check .
uv run --frozen python manage.py check
uv run --frozen python manage.py test
uv sync --frozen --no-dev
```

선택 DB로 검사·운영 설치할 때도 해당 `--extra` 옵션을 유지한다. 운영 서비스는 설치된 `.venv/bin/gunicorn`을 직접 실행한다. CI는 uv로 설치하고 잠금 파일의 최신 여부를 확인한다.

#!/usr/bin/env bash
# Run during a maintenance window with writers stopped.
# Default: SQLite. Optional engines: postgres, mariadb. Credentials stay in protected client files.
set -euo pipefail
umask 077
backup_engine=${MANUALBOOK_DB_ENGINE:-sqlite}
: "${MANUALBOOK_MEDIA_ROOT:?Set the private media directory}"
: "${MANUALBOOK_BACKUP_ROOT:?Set a protected destination}"
command -v tar >/dev/null
[[ -d "$MANUALBOOK_MEDIA_ROOT" ]] || { echo 'Media directory is missing' >&2; exit 1; }
mkdir -p "$MANUALBOOK_BACKUP_ROOT"
backup_dir=$(mktemp -d "$MANUALBOOK_BACKUP_ROOT/snapshot-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
case "$backup_engine" in
  sqlite)
    : "${MANUALBOOK_SQLITE_PATH:?Set the absolute SQLite database path}"
    python3 - "$MANUALBOOK_SQLITE_PATH" "$backup_dir/database.dump" <<'SQLITE'
import pathlib, sqlite3, sys
source = pathlib.Path(sys.argv[1])
if not source.is_absolute() or not source.is_file():
    raise SystemExit('Use an existing absolute SQLite database path')
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
    with sqlite3.connect(sys.argv[2]) as dest:
        src.backup(dest)
        if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise SystemExit('SQLite integrity check failed')
SQLITE
    ;;
  postgres)
    : "${PGSERVICE:?Set PGSERVICE for the production database}"
    pg_dump --format=custom --file="$backup_dir/database.dump"
    ;;
  mariadb)
    : "${MANUALBOOK_DB_CLIENT_FILE:?Set a protected MariaDB client option file}"
    : "${MANUALBOOK_DB_NAME:?Set the MariaDB database name}"
    mariadb-dump --defaults-extra-file="$MANUALBOOK_DB_CLIENT_FILE" --single-transaction --routines --triggers --events "$MANUALBOOK_DB_NAME" > "$backup_dir/database.dump"
    ;;
  *) echo 'Choose sqlite, postgres or mariadb' >&2; exit 1 ;;
esac
printf '%s\n' "$backup_engine" > "$backup_dir/DATABASE_ENGINE"
tar -C "$MANUALBOOK_MEDIA_ROOT" -czf "$backup_dir/private-media.tar.gz" .
(cd "$backup_dir" && sha256sum database.dump private-media.tar.gz DATABASE_ENGINE > SHA256SUMS)
printf '%s\n' "Backup created: $backup_dir" 'Encrypt and copy off-host. Back up the encryption key separately. Test restore.'

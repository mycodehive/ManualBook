#!/usr/bin/env bash
# NON-DESTRUCTIVE rehearsal: requires a newly-created EMPTY database and EMPTY media directory.
set -euo pipefail
umask 077
restore_engine=${MANUALBOOK_DB_ENGINE:-sqlite}
: "${MANUALBOOK_RESTORE_MEDIA_ROOT:?Set an empty rehearsal media directory}"
backup_dir=${1:?Usage: restore_verify.sh /absolute/snapshot-directory}
[[ -d "$backup_dir" ]] || exit 1
[[ "$backup_dir" = /* ]] || { echo 'Use an absolute snapshot path' >&2; exit 1; }
mkdir -p "$MANUALBOOK_RESTORE_MEDIA_ROOT"
[[ -z "$(ls -A "$MANUALBOOK_RESTORE_MEDIA_ROOT")" ]] || { echo 'Restore directory must be empty' >&2; exit 1; }

(cd "$backup_dir" && sha256sum -c SHA256SUMS)
# Old PostgreSQL snapshots predate the engine manifest.
snapshot_engine=postgres
if [[ -f "$backup_dir/DATABASE_ENGINE" ]]; then snapshot_engine=$(cat "$backup_dir/DATABASE_ENGINE"); fi
[[ "$restore_engine" = "$snapshot_engine" ]] || { echo 'Snapshot database engine does not match; this is not an engine migration tool' >&2; exit 1; }
case "$restore_engine" in
  sqlite)
    : "${MANUALBOOK_SQLITE_PATH:?Set a new absolute rehearsal SQLite path}"
    python3 - "$backup_dir/database.dump" "$MANUALBOOK_SQLITE_PATH" <<'SQLITE'
import pathlib, shutil, sqlite3, sys
source, target = map(pathlib.Path, sys.argv[1:])
if not target.is_absolute() or target.exists():
    raise SystemExit('Use a new absolute rehearsal SQLite path; existing files are never overwritten')
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as db:
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
        raise SystemExit('SQLite snapshot integrity check failed')
with target.open('xb') as dest, source.open('rb') as src:
    shutil.copyfileobj(src, dest)
SQLITE
    ;;
  postgres)
    : "${PGSERVICE:?Set PGSERVICE to an isolated rehearsal database}"
    [[ $(psql -Atqc "SELECT count(*) FROM pg_tables WHERE schemaname='public'") = 0 ]] || { echo 'Rehearsal database must be empty' >&2; exit 1; }
    pg_restore --exit-on-error --no-owner --no-acl --dbname="service=$PGSERVICE" "$backup_dir/database.dump"
    ;;
  mariadb)
    : "${MANUALBOOK_DB_CLIENT_FILE:?Set a protected rehearsal MariaDB client file}"
    : "${MANUALBOOK_DB_NAME:?Set the isolated rehearsal database name}"
    table_count=$(mariadb --defaults-extra-file="$MANUALBOOK_DB_CLIENT_FILE" --batch --skip-column-names "$MANUALBOOK_DB_NAME" -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()")
    [[ "$table_count" = 0 ]] || { echo 'Rehearsal database must be empty' >&2; exit 1; }
    mariadb --defaults-extra-file="$MANUALBOOK_DB_CLIENT_FILE" "$MANUALBOOK_DB_NAME" < "$backup_dir/database.dump"
    ;;
  *) echo 'Choose sqlite, postgres or mariadb' >&2; exit 1 ;;
esac
tar -C "$MANUALBOOK_RESTORE_MEDIA_ROOT" -xzf "$backup_dir/private-media.tar.gz"
printf '%s\n' 'Rehearsal data restored. Run application checks and verify publication, private files and encrypted connections with the matching key.'

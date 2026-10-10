#!/usr/bin/env bash
# NON-DESTRUCTIVE rehearsal: requires a newly-created EMPTY database and EMPTY media directory.
set -euo pipefail
umask 077
: "${PGSERVICE:?Set PGSERVICE to an isolated rehearsal database}"
: "${MANUALBOOK_RESTORE_MEDIA_ROOT:?Set an empty rehearsal media directory}"
backup_dir=${1:?Usage: restore_verify.sh /absolute/snapshot-directory}
[[ -d "$backup_dir" ]] || exit 1
[[ "$backup_dir" = /* ]] || { echo 'Use an absolute snapshot path' >&2; exit 1; }
mkdir -p "$MANUALBOOK_RESTORE_MEDIA_ROOT"
[[ -z "$(ls -A "$MANUALBOOK_RESTORE_MEDIA_ROOT")" ]] || { echo 'Restore directory must be empty' >&2; exit 1; }
[[ $(psql -Atqc "SELECT count(*) FROM pg_tables WHERE schemaname='public'") = 0 ]] || { echo 'Rehearsal database must be empty' >&2; exit 1; }
(cd "$backup_dir" && sha256sum -c SHA256SUMS)
pg_restore --exit-on-error --no-owner --no-acl --dbname="service=$PGSERVICE" "$backup_dir/database.dump"
tar -C "$MANUALBOOK_RESTORE_MEDIA_ROOT" -xzf "$backup_dir/private-media.tar.gz"
printf '%s\n' 'Rehearsal data restored. Run application checks and verify publication, private files and encrypted connections with the matching key.'

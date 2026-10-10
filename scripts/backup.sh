#!/usr/bin/env bash
# Run during a maintenance window with writers stopped.
# PGSERVICE selects a configured ~/.pg_service.conf and ~/.pgpass; no passwords in args.
set -euo pipefail
umask 077
: "${PGSERVICE:?Set PGSERVICE for the production database}"
: "${MANUALBOOK_MEDIA_ROOT:?Set the private media directory}"
: "${MANUALBOOK_BACKUP_ROOT:?Set a protected destination}"
command -v pg_dump >/dev/null
command -v tar >/dev/null
[[ -d "$MANUALBOOK_MEDIA_ROOT" ]] || { echo 'Media directory is missing' >&2; exit 1; }
mkdir -p "$MANUALBOOK_BACKUP_ROOT"
backup_dir=$(mktemp -d "$MANUALBOOK_BACKUP_ROOT/snapshot-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
pg_dump --format=custom --file="$backup_dir/database.dump"
tar -C "$MANUALBOOK_MEDIA_ROOT" -czf "$backup_dir/private-media.tar.gz" .
(cd "$backup_dir" && sha256sum database.dump private-media.tar.gz > SHA256SUMS)
printf '%s\n' "Backup created: $backup_dir" 'Encrypt and copy off-host. Back up the encryption key separately. Test restore.'

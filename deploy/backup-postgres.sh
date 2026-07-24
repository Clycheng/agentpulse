#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

set -a
source .env.production
set +a

: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"

backup_dir="${BACKUP_DIR:-$ROOT/backups}"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$backup_dir/agentpulse-$stamp.sql.gz.gpg"

docker compose -f compose.prod.yml exec -T api \
  sh -lc 'pg_dump --no-owner --no-acl "$AGENTPULSE_DATABASE_URL"' \
  | gzip -9 \
  | gpg --batch --yes --pinentry-mode loopback \
      --passphrase-fd 3 \
      3<<<"$BACKUP_ENCRYPTION_KEY" \
      --symmetric --cipher-algo AES256 --output "$target"

chmod 600 "$target"
find "$backup_dir" -type f -name 'agentpulse-*.sql.gz.gpg' -mtime +6 -delete
echo "Encrypted backup written: $target"

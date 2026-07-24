#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -f .env.production ]]; then
  echo "Missing deploy/.env.production" >&2
  exit 1
fi
if [[ "$(stat -c '%a' .env.production)" != "600" ]]; then
  echo "deploy/.env.production must have mode 600" >&2
  exit 1
fi

set -a
source .env.production
set +a

if [[ $# -gt 0 ]]; then
  AGENTPULSE_IMAGE="$1"
  export AGENTPULSE_IMAGE
fi

previous="$(docker inspect agentpulse-api-1 --format '{{.Config.Image}}' 2>/dev/null || true)"

docker compose -f compose.prod.yml pull api || docker image inspect "$AGENTPULSE_IMAGE" >/dev/null
docker compose -f compose.prod.yml build --pull caddy
docker compose -f compose.prod.yml up -d --remove-orphans

ready_url="https://${API_DOMAIN:-api.agentpulse.cc}/api/health/ready"
for _ in $(seq 1 30); do
  if curl --fail --silent --show-error --max-time 5 "$ready_url" >/dev/null; then
    docker image prune -f >/dev/null
    echo "Deployment ready: $AGENTPULSE_IMAGE"
    exit 0
  fi
  sleep 4
done

echo "Readiness failed; restoring previous API image" >&2
if [[ -n "$previous" ]]; then
  AGENTPULSE_IMAGE="$previous" docker compose -f compose.prod.yml up -d --no-deps api
fi
exit 1

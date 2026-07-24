#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./bootstrap-oracle.sh" >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl docker.io docker-compose-v2 gnupg
systemctl enable --now docker

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw default deny incoming
ufw default allow outgoing
ufw --force enable

install -d -m 0750 -o "${SUDO_USER:-root}" -g "${SUDO_USER:-root}" /opt/agentpulse
echo "Oracle host ready. Place deploy files in /opt/agentpulse and create .env.production."

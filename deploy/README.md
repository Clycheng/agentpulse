# AgentPulse production deployment

This directory is the single-node Oracle Always Free deployment described by ADR 0012. The API image pins Hermes; the Caddy image is reproducibly built from its pinned source commit and patched toolchain by Compose.

## 1. External resources

1. Create a Supabase Free project and copy its **Session Pooler** connection string (port 5432). Append `sslmode=require`.
2. Create an Ubuntu ARM64 Oracle VM with 2 OCPU / 12 GB RAM. Open ingress TCP 22, 80, and 443 in the Oracle VCN security list.
3. Add an `A` record for `api.agentpulse.cc` pointing to the VM public IP.
4. Log the VM into GHCR with a token that can read the private API image: `docker login ghcr.io -u Clycheng`.

## 2. Bootstrap and configure

```bash
sudo ./bootstrap-oracle.sh
cp .env.production.example .env.production
chmod 600 .env.production
```

Fill the Supabase URL and two independent random secrets. Never paste a user's DeepSeek or Resend key into this file; those are encrypted through the desktop app.

## 3. Deploy and back up

Deploy an immutable image digest when possible:

```bash
./deploy.sh ghcr.io/clycheng/agentpulse-api@sha256:...
curl https://api.agentpulse.cc/api/health/ready
```

`deploy.sh` pulls or accepts a preloaded API image, builds the pinned Caddy image locally, and restores the previous API image if readiness fails.

Install the encrypted daily backup at 03:20 UTC:

```cron
20 3 * * * cd /opt/agentpulse && ./backup-postgres.sh >> /var/log/agentpulse-backup.log 2>&1
```

Restore by decrypting and piping into `psql` after first stopping the API container. The backup script retains seven daily files. Caddy certificates and Hermes profile/work directories live in Docker volumes and survive container replacement.

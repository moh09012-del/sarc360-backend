# SARC360 ERP — Production Deployment Guide
**Hetzner CPX22 + Cloudflare Full (strict) + Supabase PostgreSQL**

---

## Prerequisites Checklist

Before you start, confirm you have:

| # | Item | Where to get it |
|---|------|----------------|
| 1 | Domain name (e.g. `sarc360.app`) | Namecheap, GoDaddy, or Saudi registrar |
| 2 | Cloudflare account (free tier is fine) | cloudflare.com |
| 3 | Hetzner Cloud account | hetzner.com/cloud |
| 4 | Supabase project with connection string | supabase.com |
| 5 | SSH key pair | `ssh-keygen -t ed25519 -C "sarc360-prod"` |

---

## Part 1 — Manual Steps (One-Time Setup)

### 1.1 Domain → Cloudflare DNS

1. **Add domain to Cloudflare**:
   - Login to Cloudflare → Add site → enter `sarc360.app`
   - Choose Free plan
   - Cloudflare gives you 2 nameservers (e.g. `emma.ns.cloudflare.com`)

2. **Update nameservers at your registrar**:
   - Replace existing nameservers with the two Cloudflare nameservers
   - Propagation takes 1–24 hours

3. **Add DNS records** (after you have your Hetzner server IP):

   | Type | Name | Content | Proxy |
   |------|------|---------|-------|
   | A | `api` | `<HETZNER_IP>` | Proxied (orange cloud) ✓ |
   | A | `erp` | `<HETZNER_IP>` | Proxied (orange cloud) ✓ |
   | CNAME | `www` | `erp.sarc360.app` | Proxied (orange cloud) ✓ |

4. **SSL/TLS settings** in Cloudflare:
   - SSL/TLS → Overview → Select **Full (strict)**
   - SSL/TLS → Origin Server → Create Certificate
   - Set validity: 15 years
   - Hostnames: `sarc360.app`, `*.sarc360.app`
   - Download the certificate as `origin.crt` and `origin.key`
   - Save them to: `deploy/nginx/ssl/origin.crt` and `deploy/nginx/ssl/origin.key`

### 1.2 Hetzner Server Provisioning

1. **Create server**:
   - Type: CPX22 (3 vCPU, 4GB RAM, 40GB SSD) — SAR ~35.59/month
   - Image: Ubuntu 22.04 LTS
   - Region: Helsinki (EU) or Falkenstein — or `nbg1` for lowest latency from KSA
   - Add your SSH public key

2. **First login**:
   ```bash
   ssh root@<HETZNER_IP>
   ```

3. **Create non-root user**:
   ```bash
   adduser sarc
   usermod -aG sudo sarc
   su - sarc
   ```

4. **Install Docker**:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker sarc
   # Log out and back in for group to take effect
   ```

5. **Install Docker Compose plugin**:
   ```bash
   sudo apt-get install -y docker-compose-plugin
   docker compose version   # should print v2.x.x
   ```

6. **Configure firewall (UFW)**:
   ```bash
   sudo ufw allow OpenSSH
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw --force enable
   sudo ufw status
   ```

---

## Part 2 — Automated Deployment Steps

Run these on the Hetzner server as the `sarc` user.

### 2.1 Clone and configure

```bash
cd ~
git clone https://github.com/YOUR_ORG/sarc360-backend.git
cd sarc360-backend

# Copy the SSL certs you downloaded from Cloudflare
mkdir -p deploy/nginx/ssl
# Transfer via scp from your laptop:
#   scp origin.crt sarc@<HETZNER_IP>:~/sarc360-backend/deploy/nginx/ssl/
#   scp origin.key sarc@<HETZNER_IP>:~/sarc360-backend/deploy/nginx/ssl/

# Set up environment
cp deploy/.env.production .env
nano .env   # Fill in all CHANGE_ME values
```

### 2.2 Build and start

```bash
# Build production image
docker compose build

# Start all services
docker compose up -d

# Check logs
docker compose logs -f api
```

### 2.3 Run migrations

```bash
docker compose exec api alembic upgrade head
```

### 2.4 Create production admin user

```bash
docker compose exec api python scripts/create_admin.py
# Or use the manual script approach from the previous session
```

### 2.5 Verify

```bash
# Health check via Cloudflare proxy
curl -sS https://api.sarc360.app/health | python3 -m json.tool

# Expected:
# {
#   "status": "ok",
#   "app": "SARC360 ERP",
#   "db": "ok",
#   "migration": "a1b2c3d4e5f6"
# }
```

---

## Part 3 — Ongoing Operations

### Updating the application

```bash
cd ~/sarc360-backend
git pull origin main
docker compose build
docker compose up -d --no-deps api
docker compose exec api alembic upgrade head
```

### Viewing logs

```bash
docker compose logs -f api          # Application logs
docker compose logs -f nginx        # Nginx access/error logs
tail -f deploy/nginx/logs/access.log
```

### Database backup (manual)

```bash
# Supabase provides automatic daily backups on paid plans.
# For manual backup from Supabase:
pg_dump "$(grep DATABASE_URL .env | cut -d= -f2-)" \
  --no-password -Fc \
  -f "backup_$(date +%Y%m%d_%H%M%S).dump"
```

### Scheduled backup (cron — add after server stabilisation)

```bash
# Add to crontab: crontab -e
# Daily backup at 02:00 Asia/Riyadh (UTC-3 = 23:00 UTC)
0 23 * * * cd ~/sarc360-backend && pg_dump "$DATABASE_URL" -Fc -f backups/backup_$(date +\%Y\%m\%d).dump && find backups/ -name "*.dump" -mtime +30 -delete
```

---

## Part 4 — Deployment Readiness Checklist

| # | Check | Status |
|---|-------|--------|
| 1 | Domain registered and pointing to Cloudflare | ⚠️ Manual |
| 2 | Cloudflare SSL mode = Full (strict) | ⚠️ Manual |
| 3 | Cloudflare Origin Certificate generated + saved to `deploy/nginx/ssl/` | ⚠️ Manual |
| 4 | DNS records: A @ api → Hetzner IP (proxied) | ⚠️ Manual |
| 5 | Hetzner CPX22 server provisioned with Ubuntu 22.04 | ⚠️ Manual |
| 6 | Docker + Docker Compose installed on server | ⚠️ Manual |
| 7 | UFW firewall: only 22/80/443 open | ⚠️ Manual |
| 8 | `.env` filled in (all CHANGE_ME replaced) | ⚠️ Manual |
| 9 | SSL certs transferred to `deploy/nginx/ssl/` | ⚠️ Manual |
| 10 | `docker compose up -d` runs without errors | ⚠️ Automated |
| 11 | `alembic upgrade head` shows current revision | ⚠️ Automated |
| 12 | `curl https://api.sarc360.app/health` returns `"status":"ok"` | ⚠️ Automated |
| 13 | Admin login works via frontend | ⚠️ Automated |
| 14 | ZATCA_CSID set (after certificate approval, 2-4 weeks) | ⚠️ Pending |
| 15 | MUDAD_API_KEY set (after WPS account setup) | ⚠️ Pending |
| 16 | Supabase daily backups enabled (paid plan) or cron configured | ⚠️ Pending |
| 17 | Cloudflare WAF rules: block non-KSA traffic (optional) | ⚠️ Pending |

---

## Part 5 — Cloudflare WAF Rules (Optional, Recommended)

After going live, add these in **Cloudflare → Security → WAF → Custom Rules**:

**Rule 1: Restrict admin endpoints to KSA IPs only**
```
(http.request.uri.path contains "/auth/" and ip.geoip.country ne "SA")
→ Action: Block
```

**Rule 2: Block known bad bots**
```
(cf.client.bot)
→ Action: Block
```

**Rule 3: Rate limit login attempts**
```
(http.request.uri.path eq "/auth/login")
→ Action: Rate Limit (5 requests / 1 minute per IP)
```

---

## Architecture Summary

```
Internet
   │
   ▼
Cloudflare (DNS + WAF + DDoS protection + SSL termination to origin)
   │ HTTPS (Full strict — Cloudflare ↔ Origin uses real cert)
   ▼
Hetzner CPX22
   ├── Nginx (80→443 redirect, rate limiting, proxy headers)
   │       │
   │       ▼
   │   FastAPI via Gunicorn/UvicornWorker (port 8001 internal)
   │
   ├── Redis (task queue, rate limits)
   │
   └── Supabase (managed PostgreSQL, external)
```

---

*SARC360 ERP — Generated 2026-03-28 | شركة سما الروابي للمقاولات*

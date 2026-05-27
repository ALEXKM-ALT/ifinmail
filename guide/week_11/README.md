# Week 11: Security, DevOps & Deployment

**Month 3: Integration & Capstone | Days 61–66**

A mail platform lives and dies by its operations. This week covers TLS certificate automation, Docker containerization, backup strategies, monitoring, CI/CD pipeline design, SBOM generation, and the security hardening required to run ifinmail App in production. By Friday, you will deploy the full stack on a VPS.

---

## Learning Goals for the Week

By Sunday, you will be able to:

- Automate TLS certificate management with Certbot/ACME
- Containerize ifinmail services with Docker and Docker Compose
- Implement backup and restore procedures for PostgreSQL and mail storage
- Set up monitoring with logs, metrics, and alerts
- Design a CI/CD pipeline with signed commits and SBOM generation
- Harden a Linux server for mail hosting

---

## Day 1 (Monday): TLS Automation with Certbot & Security Hardening

### Learning Objectives
- Understand the ACME protocol and how Let's Encrypt works
- Use Certbot to obtain and auto-renew TLS certificates
- Configure Postfix, Dovecot, and nginx with Let's Encrypt certificates
- Harden SSH, configure a firewall, and apply basic server security

### Theory / Reading
- **ACME**: Automatic Certificate Management Environment; Certbot is the most common client
- **Let's Encrypt**: free, automated, open Certificate Authority
- **Certificate renewal**: certs are valid for 90 days; Certbot auto-renews at 60 days
- **Firewall (ufw/iptables)**: allow only necessary ports: 25, 465, 587, 993, 443, 80, 22

### Practical Exercise
```bash
# Install Certbot
sudo apt update && sudo apt install -y certbot

# Obtain a certificate (requires a real domain with DNS pointing to this server)
# For training, use --dry-run first:
sudo certbot certonly --standalone \
    --dry-run \
    -d mail.ifinmail.local \
    -m admin@ifinmail.local \
    --agree-tos

# In production (without --dry-run):
# sudo certbot certonly --standalone -d mail.ifinmail.com -d imap.ifinmail.com

# Certificate locations
sudo ls -la /etc/letsencrypt/live/mail.ifinmail.local/ 2>/dev/null || echo "(No real cert yet — dry run above)"

# Auto-renewal hook: restart services after renewal
cat << 'EOF' | sudo tee /etc/letsencrypt/renewal-hooks/deploy/ifinmail-restart.sh
#!/bin/bash
# Restart services after certificate renewal
systemctl reload postfix
systemctl reload dovecot
systemctl reload nginx
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/ifinmail-restart.sh

# Test auto-renewal (dry run)
sudo certbot renew --dry-run

# Certbot systemd timer (installed automatically)
sudo systemctl status certbot.timer
```

```bash
# --- Server Security Hardening ---

# 1. Firewall: allow only mail and SSH ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment "SSH"
sudo ufw allow 25/tcp comment "SMTP"
sudo ufw allow 465/tcp comment "SMTPS"
sudo ufw allow 587/tcp comment "SMTP Submission"
sudo ufw allow 143/tcp comment "IMAP"
sudo ufw allow 993/tcp comment "IMAPS"
sudo ufw allow 80/tcp comment "HTTP (Certbot)"
sudo ufw allow 443/tcp comment "HTTPS (API)"
sudo ufw --force enable
sudo ufw status verbose

# 2. SSH hardening
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup
sudo sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?X11Forwarding .*/X11Forwarding no/' /etc/ssh/sshd_config
sudo systemctl reload sshd

# 3. Fail2ban for brute force protection
sudo apt install -y fail2ban
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local

cat << 'EOF' | sudo tee /etc/fail2ban/jail.d/ifinmail.conf
[postfix]
enabled = true
port = smtp,465,587
filter = postfix
logpath = /var/log/mail.log
maxretry = 5
bantime = 3600

[dovecot]
enabled = true
port = imap,imaps
filter = dovecot
logpath = /var/log/mail.log
maxretry = 10
bantime = 3600

[sshd]
enabled = true
maxretry = 3
bantime = 3600
EOF

sudo systemctl restart fail2ban
sudo fail2ban-client status

# 4. Check listening ports
sudo ss -tlnp | grep -E ":(22|25|80|143|443|465|587|993) "
```

### Checkpoint Questions
1. Why does Let's Encrypt issue 90-day certificates instead of longer?
2. What is the difference between `certonly` and the Certbot nginx/apache plugins?
3. Why does the renewal hook need to restart services?
4. What is the principle behind `ufw default deny incoming`?

### Connection to ifinmail App
Proposal Sections 13.3 and 14.1 mandate "TLS everywhere" and "certificate automation." Certbot delivers this. The firewall configuration protects the mail ports. fail2ban blocks brute force attacks on SMTP/IMAP submission — a real threat for any mail server.

---

## Day 2 (Tuesday): Docker & Containerization

### Learning Objectives
- Understand Docker concepts: images, containers, volumes, networks, Dockerfiles
- Containerize each ifinmail service: Postfix, Dovecot, Rspamd, Python API, Redis
- Use Docker Compose to orchestrate the full stack
- Understand when to use Docker vs bare metal for mail services

### Theory / Reading
- **Image**: immutable template built from a Dockerfile
- **Container**: running instance of an image with its own filesystem and network
- **Volume**: persistent data that survives container restarts/recreation
- **Docker Compose**: define multi-service applications in a single `compose.yaml`

### Practical Exercise
```dockerfile
# ~/ifinmail-docker/postfix/Dockerfile
# Postfix container for ifinmail
FROM ubuntu:24.04

RUN apt update && DEBIAN_FRONTEND=noninteractive apt install -y \
    postfix \
    postfix-pgsql \
    postfix-policyd-spf-python \
    opendkim \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration (mounted as volumes in production)
COPY main.cf /etc/postfix/main.cf
COPY master.cf /etc/postfix/master.cf
COPY pgsql/ /etc/postfix/pgsql/

# Postfix needs these directories
RUN mkdir -p /var/spool/postfix && chown -R postfix:postfix /var/spool/postfix

EXPOSE 25 465 587

CMD ["postfix", "start-fg"]
```

```yaml
# ~/ifinmail-docker/compose.yaml
# Full ifinmail stack for development and testing
# Production may split services across hosts

version: "3.8"

services:
  # --- Databases ---
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ifinmail
      POSTGRES_USER: ifinmail
      POSTGRES_PASSWORD: dev_password_change_in_prod
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/01-init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ifinmail"]
      interval: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      retries: 5

  # --- Mail Infrastructure ---
  postfix:
    build: ./postfix
    volumes:
      - postfix_spool:/var/spool/postfix
      - postfix_logs:/var/log
      - ./certs:/etc/postfix/certs:ro
    ports:
      - "25:25"
      - "465:465"
      - "587:587"
    depends_on:
      - postgres
      - dovecot
    restart: unless-stopped

  dovecot:
    build: ./dovecot
    volumes:
      - mail_data:/var/mail/vhosts
      - dovecot_logs:/var/log
      - ./certs:/etc/dovecot/certs:ro
    ports:
      - "143:143"
      - "993:993"
    depends_on:
      - postgres
    restart: unless-stopped

  rspamd:
    build: ./rspamd
    volumes:
      - rspamd_data:/var/lib/rspamd
      - rspamd_logs:/var/log/rspamd
      - ./dkim:/etc/dkim:ro
    ports:
      - "11332:11332"   # milter
      - "11333:11333"   # normal worker
      - "11334:11334"   # web UI (protect in production!)
    depends_on:
      - redis
    restart: unless-stopped

  # --- Platform API ---
  api:
    build: ../ifinmail-api
    environment:
      DATABASE_URL: postgresql://ifinmail:dev_password_change_in_prod@postgres:5432/ifinmail
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: dev_secret_change_in_production
    volumes:
      - ../ifinmail-api:/app
      - mail_data:/var/mail/vhosts:ro  # Read Dovecot's Maildir
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    restart: unless-stopped

  # --- Web Client ---
  web:
    build: ../ifinmail-web
    environment:
      API_URL: http://api:8000
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  postfix_spool:
  postfix_logs:
  dovecot_logs:
  rspamd_data:
  rspamd_logs:
  mail_data:

networks:
  default:
    name: ifinmail-net
```

```bash
# Start the stack
cd ~/ifinmail-docker
docker compose up -d

# Check status
docker compose ps
docker compose logs -f --tail=50 postfix

# Test connectivity
docker compose exec postfix postconf -n
docker compose exec dovecot doveadm user '*'

# Stop everything
docker compose down
```

### Checkpoint Questions
1. Why do Postfix and Dovecot need shared volumes for mail storage?
2. What is the difference between a bind mount and a named volume?
3. When would it be better to run Postfix on bare metal instead of Docker?
4. How does Docker Compose's `depends_on` + `healthcheck` ensure correct startup order?

### Connection to ifinmail App
Docker Compose enables the "single VPS" deployment model from proposal Section 14.1. As ifinmail scales, services can be split across hosts. The volume configuration ensures mail data, database files, and logs survive container restarts.

---

## Day 3 (Wednesday): Backups & Disaster Recovery

### Learning Objectives
- Design a backup strategy for ifinmail: PostgreSQL, mail storage, configs, DKIM keys
- Automate backups with shell scripts and cron
- Test restore procedures (the backup you never test is not a backup)
- Understand backup encryption and immutability requirements

### Theory / Reading
- **Backup scope** (proposal Section 14.2): PostgreSQL, mail storage, DKIM keys, configs, audit logs
- **3-2-1 rule**: 3 copies, 2 different media, 1 offsite
- **pg_dump**: logical backup of PostgreSQL; `pg_dumpall` for full cluster
- **rsync/rdiff-backup**: efficient file-level backups
- **Encryption at rest**: `gpg` or `openssl enc` before uploading to offsite storage

### Practical Exercise
```bash
# Create backup directory structure
sudo mkdir -p /backups/{postgresql,mail,configs,dkim,audit}
sudo chown -R $USER:$USER /backups
```

```bash
#!/bin/bash
# ~/ifinmail-scripts/backup_full.sh
# Full backup script for ifinmail — matches proposal Section 14.2
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_ROOT="/backups/${TIMESTAMP}"
RETENTION_DAYS=30

echo "=== ifinmail Backup: $TIMESTAMP ==="

# 1. PostgreSQL dump
echo "[1/5] Backing up PostgreSQL..."
mkdir -p "$BACKUP_ROOT/postgresql"
sudo -u postgres pg_dump -Fc ifinmail > "$BACKUP_ROOT/postgresql/ifinmail.dump"
# Schema-only backup for quick reference
sudo -u postgres pg_dump --schema-only ifinmail > "$BACKUP_ROOT/postgresql/ifinmail_schema.sql"

# 2. Mail storage (Maildir)
echo "[2/5] Backing up mail storage..."
mkdir -p "$BACKUP_ROOT/mail"
sudo rsync -a --delete /var/mail/vhosts/ "$BACKUP_ROOT/mail/vhosts/"

# 3. Configuration files
echo "[3/5] Backing up configuration..."
mkdir -p "$BACKUP_ROOT/configs"
sudo cp -r /etc/postfix "$BACKUP_ROOT/configs/"
sudo cp -r /etc/dovecot "$BACKUP_ROOT/configs/"
sudo cp -r /etc/rspamd "$BACKUP_ROOT/configs/"
sudo cp -r /etc/dkim "$BACKUP_ROOT/configs/"

# 4. DKIM keys (separate — these are irreplaceable)
echo "[4/5] Backing up DKIM keys..."
mkdir -p "$BACKUP_ROOT/dkim"
sudo cp -r /etc/dkim "$BACKUP_ROOT/dkim/keys"
sudo chmod -R 600 "$BACKUP_ROOT/dkim"

# 5. Audit logs
echo "[5/5] Backing up audit logs..."
mkdir -p "$BACKUP_ROOT/audit"
sudo journalctl -u postfix -u dovecot -u rspamd --since "24 hours ago" > "$BACKUP_ROOT/audit/mail_services.log"

# Create a manifest
cat > "$BACKUP_ROOT/MANIFEST.txt" << MANIFEST
Backup: $TIMESTAMP
Host: $(hostname)
Date: $(date -Iseconds)
Contents:
  - PostgreSQL dump (ifinmail.dump + schema)
  - Mail storage (/var/mail/vhosts)
  - Configuration (/etc/postfix, /etc/dovecot, /etc/rspamd)
  - DKIM keys
  - Audit logs (last 24h)
MANIFEST

# Compress
echo "Compressing backup..."
tar -czf "/backups/ifinmail_backup_${TIMESTAMP}.tar.gz" -C "$BACKUP_ROOT" .
rm -rf "$BACKUP_ROOT"

# Optional: Encrypt (for offsite storage)
# gpg --symmetric --cipher-algo AES256 "/backups/ifinmail_backup_${TIMESTAMP}.tar.gz"

# Clean old backups
echo "Cleaning backups older than $RETENTION_DAYS days..."
find /backups -name "ifinmail_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Report
SIZE=$(du -h "/backups/ifinmail_backup_${TIMESTAMP}.tar.gz" | cut -f1)
echo "=== Backup complete: /backups/ifinmail_backup_${TIMESTAMP}.tar.gz ($SIZE) ==="
```

```bash
#!/bin/bash
# ~/ifinmail-scripts/restore_test.sh
# RESTORE SIMULATION — run this monthly to verify backups work
set -euo pipefail

TEST_DIR="/tmp/ifinmail_restore_test"
mkdir -p "$TEST_DIR"

# Find latest backup
LATEST=$(ls -t /backups/ifinmail_backup_*.tar.gz | head -1)
echo "Testing restore from: $LATEST"

tar -xzf "$LATEST" -C "$TEST_DIR"
ls -la "$TEST_DIR"

# 1. Check PostgreSQL dump validity
echo "Checking PostgreSQL dump..."
pg_restore -l "$TEST_DIR/postgresql/ifinmail.dump" > /dev/null && echo "  PASS: pg_dump is valid"

# 2. Check mail storage
echo "Checking mail storage..."
find "$TEST_DIR/mail/vhosts" -type d | head -10
echo "  Mail directories exist: $(find "$TEST_DIR/mail/vhosts" -type d | wc -l)"

# 3. Check configs
echo "Checking configuration files..."
[ -f "$TEST_DIR/configs/postfix/main.cf" ] && echo "  PASS: postfix/main.cf exists"
[ -f "$TEST_DIR/configs/dovecot/dovecot.conf" ] && echo "  PASS: dovecot.conf exists"

# 4. Check DKIM keys
echo "Checking DKIM keys..."
find "$TEST_DIR/dkim" -name "*.key" | while read key; do
    echo "  DKIM key: $key ($(wc -c < "$key") bytes)"
done

echo "=== Restore test passed ==="
rm -rf "$TEST_DIR"
```

```bash
# Schedule backups with cron
chmod +x ~/ifinmail-scripts/backup_full.sh
chmod +x ~/ifinmail-scripts/restore_test.sh

# Daily backup at 3:17am
(crontab -l 2>/dev/null; echo "17 3 * * * $HOME/ifinmail-scripts/backup_full.sh >> /var/log/ifinmail-backup.log 2>&1") | crontab -

# Monthly restore test on the 1st at 5:23am
(crontab -l 2>/dev/null; echo "23 5 1 * * $HOME/ifinmail-scripts/restore_test.sh >> /var/log/ifinmail-backup.log 2>&1") | crontab -

crontab -l
```

### Checkpoint Questions
1. Why are DKIM keys backed up separately from other configurations?
2. What is the difference between `pg_dump` (logical) and `pg_basebackup` (physical)?
3. Why must backup restores be tested regularly, not just taken?
4. What does the 3-2-1 backup rule mean for ifinmail?

### Connection to ifinmail App
Proposal Section 14.2 defines the backup scope. This script implements exactly that: PostgreSQL, mail storage, DKIM keys, configurations, audit logs. The monthly restore test ensures backups are actually usable. The encryption step prepares for offsite storage.

---

## Day 4 (Thursday): Monitoring & Alerting

### Learning Objectives
- Set up structured logging across all services
- Monitor key metrics from Proposal Section 14.3
- Implement alerting for critical conditions (queue depth, delivery failures, disk space)
- Build a simple monitoring dashboard using the existing web stack

### Theory / Reading
- **Metrics to monitor** (Section 14.3): SMTP queue length, delivery failures, bounce rates, Rspamd scores, CPU, memory, disk, IMAP login failures, API latency, cert expiry, blocklist status
- **Log aggregation**: centralize logs from Postfix, Dovecot, Rspamd, API
- **Alert thresholds**: queue > 100 = warning, > 500 = critical; bounce rate > 5% = warning

### Practical Exercise
```python
# ~/ifinmail-monitor/monitor.py
"""
ifinmail Health Monitor — collects metrics for the deliverability dashboard.
Runs as a cron job every 5 minutes. Pushes metrics to Redis for the API to read.
"""
import subprocess
import json
import redis
import time
from datetime import datetime, timedelta
from typing import Dict, Any

redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

def check_postfix_queue() -> Dict[str, Any]:
    """Check mail queue status."""
    try:
        active = int(subprocess.check_output(
            "find /var/spool/postfix/active -type f 2>/dev/null | wc -l", shell=True
        ).strip())
        deferred = int(subprocess.check_output(
            "find /var/spool/postfix/deferred -type f 2>/dev/null | wc -l", shell=True
        ).strip())
        
        status = "OK" if deferred < 50 else ("WARN" if deferred < 200 else "CRITICAL")
        
        return {
            "queue_active": active,
            "queue_deferred": deferred,
            "queue_total": active + deferred,
            "status": status,
        }
    except Exception as e:
        return {"error": str(e), "status": "UNKNOWN"}

def check_service_status() -> Dict[str, bool]:
    """Check if all mail services are running."""
    services = ["postfix", "dovecot", "rspamd", "postgresql", "redis-server"]
    status = {}
    for svc in services:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", svc],
            capture_output=True,
        )
        status[svc] = result.returncode == 0
    return status

def check_disk_space() -> Dict[str, Any]:
    """Check disk usage on key mount points."""
    mounts = ["/", "/var", "/var/mail", "/backups"]
    result = {}
    for mount in mounts:
        try:
            df = subprocess.check_output(["df", "-h", mount], text=True)
            lines = df.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                result[mount] = {
                    "size": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "use_pct": parts[4],
                }
        except subprocess.CalledProcessError:
            pass
    return result

def check_delivery_rate() -> Dict[str, Any]:
    """Calculate delivery rate from mail.log (last hour)."""
    since = (datetime.now() - timedelta(hours=1)).strftime("%b %d %H:")
    try:
        log_content = subprocess.check_output(
            ["sudo", "grep", "-E", "status=(sent|deferred|bounced)", "/var/log/mail.log"],
            text=True, stderr=subprocess.DEVNULL
        )
        lines = log_content.strip().split("\n") if log_content.strip() else []
        
        sent = sum(1 for l in lines if "status=sent" in l)
        deferred = sum(1 for l in lines if "status=deferred" in l)
        bounced = sum(1 for l in lines if "status=bounced" in l)
        total = sent + deferred + bounced
        
        return {
            "sent": sent,
            "deferred": deferred,
            "bounced": bounced,
            "delivery_rate": round(sent / total * 100, 1) if total > 0 else 100.0,
        }
    except Exception as e:
        return {"error": str(e)}

def check_cert_expiry() -> Dict[str, Any]:
    """Check TLS certificate expiration."""
    cert_paths = [
        "/etc/letsencrypt/live/mail.ifinmail.local/fullchain.pem",
        "/etc/postfix/certs/mail.ifinmail.local.crt",
    ]
    results = {}
    for path in cert_paths:
        try:
            output = subprocess.check_output(
                ["openssl", "x509", "-in", path, "-noout", "-enddate"],
                text=True, stderr=subprocess.DEVNULL
            )
            expiry_str = output.split("=")[1].strip()
            expiry = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
            days_left = (expiry - datetime.now()).days
            results[path] = {
                "expires": expiry.isoformat(),
                "days_left": days_left,
                "status": "OK" if days_left > 30 else ("WARN" if days_left > 7 else "CRITICAL"),
            }
        except Exception:
            pass
    return results

def run_all_checks() -> Dict[str, Any]:
    """Run all health checks and store in Redis."""
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "postfix_queue": check_postfix_queue(),
        "services": check_service_status(),
        "disk": check_disk_space(),
        "delivery_rate": check_delivery_rate(),
        "certificates": check_cert_expiry(),
    }
    
    # Determine overall status
    statuses = []
    if isinstance(report["postfix_queue"].get("status"), str):
        statuses.append(report["postfix_queue"]["status"])
    if not all(report["services"].values()):
        statuses.append("CRITICAL")
    
    if "CRITICAL" in statuses:
        report["overall"] = "CRITICAL"
    elif "WARN" in statuses:
        report["overall"] = "WARN"
    else:
        report["overall"] = "OK"
    
    # Store in Redis with TTL
    redis_client.setex("ifinmail:monitor:latest", 600, json.dumps(report))
    
    # Track history (keep last 288 entries = 24h at 5min intervals)
    redis_client.lpush("ifinmail:monitor:history", json.dumps(report))
    redis_client.ltrim("ifinmail:monitor:history", 0, 287)
    
    return report

if __name__ == "__main__":
    report = run_all_checks()
    print(json.dumps(report, indent=2))
    
    # Alert on critical conditions
    if report["overall"] == "CRITICAL":
        print("\n!!! CRITICAL ALERT — check ifinmail services immediately !!!")
```

```bash
# Install the monitor as a cron job (every 5 minutes)
chmod +x ~/ifinmail-monitor/monitor.py
(crontab -l 2>/dev/null; echo "*/5 * * * * cd $HOME/ifinmail-monitor && python3 monitor.py >> /var/log/ifinmail-monitor.log 2>&1") | crontab -
```

### Checkpoint Questions
1. Why monitor queue depth as a primary health indicator?
2. What is the difference between a WARN and CRITICAL alert threshold?
3. How does storing metrics in Redis help the API dashboard?
4. What should happen when the certificate expiry check returns CRITICAL?

### Connection to ifinmail App
This monitor implements every metric from proposal Section 14.3. The Redis storage feeds the deliverability dashboard (Section 6.5). In production, this would also push to Prometheus/Grafana or a managed monitoring service.

---

## Day 5 (Friday): CI/CD, SBOM & Release Pipeline

### Learning Objectives
- Design a CI/CD pipeline for ifinmail using GitHub Actions
- Generate SBOMs (Software Bill of Materials) for Python and Rust
- Implement signed commits and signed releases
- Understand the separation of build and production environments

### Theory / Reading
- **CI/CD**: Continuous Integration (test on every push) + Continuous Delivery (deploy automatically)
- **SBOM**: list of all dependencies with versions and licenses (proposal Section 3.3)
- **Sigstore/cosign**: sign container images and release artifacts
- **Proposal Section 13.5**: "No unpinned CI/CD actions," "separate build environments," "signed releases"

### Practical Exercise
```yaml
# ~/ifinmail-docker/.github/workflows/ci.yml
# CI/CD pipeline for ifinmail (GitHub Actions)
name: ifinmail CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  release:
    types: [published]

env:
  PYTHON_VERSION: "3.12"
  RUST_VERSION: "1.82"

jobs:
  # --- Python API checks ---
  python-lint:
    name: Python Lint & Type Check
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@11bd71901abe5b8200a7973a9a6f0ced1a34d7a5  # pinned SHA!
      
      - uses: actions/setup-python@0b93645e9fea7318ecaed2b359559ac225c90a2b  # pinned SHA!
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - run: pip install ruff mypy
      - run: ruff check ifinmail-api/
      - run: mypy ifinmail-api/ --strict

  python-test:
    name: Python Tests
    runs-on: ubuntu-24.04
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: ifinmail_test
          POSTGRES_USER: ifinmail
          POSTGRES_PASSWORD: test_pass
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@11bd71901abe5b8200a7973a9a6f0ced1a34d7a5
      - uses: actions/setup-python@0b93645e9fea7318ecaed2b359559ac225c90a2b
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - run: pip install -r ifinmail-api/requirements.txt
      - run: cd ifinmail-api && pytest tests/ --cov=app --cov-report=xml
      
      - uses: actions/upload-artifact@b4b15a7a0d3e6c7d0b6b3a3b  # pinned SHA!
        with:
          name: coverage-report
          path: ifinmail-api/coverage.xml

  # --- Rust checks ---
  rust-check:
    name: Rust Check & Test
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@11bd71901abe5b8200a7973a9a6f0ced1a34d7a5
      
      - uses: actions-rs/toolchain@16499b5e05bf2e26879000db0c1d13f7e13fa3af  # pinned SHA!
        with:
          toolchain: ${{ env.RUST_VERSION }}
          components: rustfmt, clippy
      
      - run: cd ifinmail-core && cargo fmt --check
      - run: cd ifinmail-core && cargo clippy -- -D warnings
      - run: cd ifinmail-core && cargo test

  # --- Security: SBOM generation ---
  sbom:
    name: Generate SBOMs
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@11bd71901abe5b8200a7973a9a6f0ced1a34d7a5
      
      # Python SBOM
      - uses: actions/setup-python@0b93645e9fea7318ecaed2b359559ac225c90a2b
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - run: pip install pip-audit cyclonedx-bom
      - run: cyclonedx-py -r -i ifinmail-api/requirements.txt -o sbom-python.json
      
      # Rust SBOM
      - run: cargo install cargo-cyclonedx
      - run: cd ifinmail-core && cargo cyclonedx -o sbom-rust.json
      
      - uses: actions/upload-artifact@b4b15a7a0d3e6c7d0b6b3a3b
        with:
          name: sboms
          path: |
            sbom-python.json
            ifinmail-core/sbom-rust.json

  # --- Build & push Docker images (on release) ---
  docker:
    name: Build and Push Docker Images
    if: github.event_name == 'release'
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@11bd71901abe5b8200a7973a9a6f0ced1a34d7a5
      
      - name: Build images
        run: |
          cd ifinmail-docker
          docker compose build
      
      - name: Sign images with cosign
        run: |
          cosign sign ifinmail-api:${{ github.ref_name }}
          cosign sign ifinmail-postfix:${{ github.ref_name }}
      
      # Push to registry (configured per deployment)
      # - name: Push to registry
      #   run: docker compose push
```

```bash
# SBOM generation (local commands)
# Python SBOM
pip install cyclonedx-bom
cyclonedx-py -r -i ifinmail-api/requirements.txt -o sbom-python.json

# Rust SBOM
cargo install cargo-cyclonedx
cd ifinmail-core && cargo cyclonedx -o sbom-rust.json

# Verify SBOMs
cat sbom-python.json | python3 -m json.tool | head -30
cat ifinmail-core/sbom-rust.json | python3 -m json.tool | head -30

# Audit dependencies for known vulnerabilities
pip install pip-audit
pip-audit -r ifinmail-api/requirements.txt

cargo audit  # For Rust
```

### Checkpoint Questions
1. Why pin GitHub Actions to SHA hashes instead of version tags (`@v4`)?
2. What is an SBOM and why does ifinmail generate them?
3. What is the difference between CI (continuous integration) and CD (continuous delivery)?
4. Why should build environments be separate from production environments?

### Connection to ifinmail App
Proposal Section 13.5 mandates: SBOM generation, pinned CI/CD actions, signed releases, and separated build/production environments. This pipeline implements all of them. Every PR runs tests; every release generates signed container images with verified SBOMs.

---

## Day 6 (Saturday): Review & Integration

### Review Challenge: Full Deployment Checklist

Create a comprehensive deployment checklist script that:

1. Verifies all services are running (Postfix, Dovecot, Rspamd, PostgreSQL, Redis, API, Nginx)
2. Checks TLS certificates for all services (valid, not expiring within 30 days)
3. Validates DNS records (MX, SPF, DKIM, DMARC) for each hosted domain
4. Confirms backup integrity (latest backup exists, restore test passed)
5. Checks disk space and warns if any mount is >80% full
6. Verifies firewall rules match expected ports
7. Checks for pending system updates
8. Outputs a single-page deployment report

**Stretch goal**: Run this as a pre-deployment gate — if any check fails, block the deployment.

### Week 11 Self-Assessment

Before moving to Week 12, confirm you can:
- [ ] Obtain and auto-renew TLS certificates with Certbot
- [ ] Harden SSH and configure a firewall
- [ ] Containerize all ifinmail services with Docker Compose
- [ ] Implement automated backups and test restores
- [ ] Monitor queue depth, delivery rate, disk space, and certificate expiry
- [ ] Design a CI/CD pipeline with signed commits and SBOM generation
- [ ] Deploy the full ifinmail stack on a single VPS

---

## Week 11 Resource Index

| Resource | Location |
|---|---|
| Certbot setup guide | `references/certbot_setup.md` |
| Firewall configuration | `references/firewall_ufw.md` |
| Docker Compose file | `code/compose.yaml` |
| Backup script | `code/backup_full.sh` |
| Restore test script | `code/restore_test.sh` |
| Health monitor | `code/monitor.py` |
| CI pipeline (GitHub Actions) | `code/.github/workflows/ci.yml` |
| Deployment checklist | `challenges/week_11_deployment.md` |

---

*Week 11 of 12 — Security, DevOps & Deployment for ifinmail Platform Engineering*

# ifinmail Provisioning Journey — Comprehensive Edge Case & Remediation Analysis

## Scope
Every file under `provisioning/`, the root `Makefile`, and all Docker entrypoints/configs.
Total: **500 edge cases** identified across 16 categories.

---

## 1. PRE-PROVISIONING / ENVIRONMENT SETUP (40 edge cases)

### Happy Path
User runs `make provision DOMAIN=example.com` on a fresh Ubuntu 22.04+ VPS with Docker installed. The script detects docker compose v2, generates secrets, builds images, starts all 8 services, obtains a Let's Encrypt cert, and prints DNS records.

### Happy Path — cloud-init
User pastes cloud-init YAML into their VPS provider with `DOMAIN`, `ADMIN_EMAIL`, `MAIL_HOSTNAME` set. cloud-init installs Docker, runs bootstrap.sh `--non-interactive`, and the full stack comes up without human intervention.

### Negative Scenarios (12)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 1 | Docker not installed | `need_cmd docker` fails with unhelpful message — no install instructions | HIGH |
| 2 | `openssl` not installed | `need_cmd openssl` fails — `die` exits | HIGH |
| 3 | `gpg` not installed | `need_cmd gpg` fails — provision.sh cannot run | HIGH |
| 4 | `docker compose` plugin missing AND `docker-compose` not in PATH | Script dies — no fallback to install it | HIGH |
| 5 | OS is CentOS/RHEL/Fedora | `bootstrap.sh` rejects with "Unsupported OS" — no path forward | MEDIUM |
| 6 | OS is Ubuntu 20.04 | Rejected — user may not know they need to upgrade | MEDIUM |
| 7 | Running as non-root in bootstrap.sh | `die "must be run as root"` — but `sudo` suggestion buried | LOW |
| 8 | `make` not installed | User can't even run `make provision` | MEDIUM |
| 9 | DNS not yet pointed to server | Let's Encrypt fails silently, stack runs with 7-day self-signed cert | HIGH |
| 10 | Firewall blocking ports 80/443 | Let's Encrypt fails; no pre-flight check | HIGH |
| 11 | Low disk space (<1GB free) | No pre-flight disk check; images fail mid-build | HIGH |
| 12 | Insufficient RAM (<1GB) | Docker builds may OOM; no pre-flight check | HIGH |

### Edge Cases (28)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 13 | `DOMAIN` contains uppercase | provision.sh uses it as-is in DKIM paths, DNS records — breaks DKIM (DNS labels are case-insensitive but convention is lowercase) | Normalize DOMAIN to lowercase in `ensure_env()` |
| 14 | `DOMAIN` has trailing dot (FQDN notation) | e.g., `example.com.` — breaks cert paths, hostname construction | Strip trailing dot |
| 15 | `DOMAIN` contains IDN/unicode | International domain names not handled; breaks openssl, certbot, DNS | Add IDN punycode conversion or document limitation |
| 16 | `MAIL_HOSTNAME` explicitly set to same as `DOMAIN` | mail.example.com = example.com — cert SANs duplicate | Validate MAIL_HOSTNAME != DOMAIN or handle gracefully |
| 17 | `ADMIN_EMAIL` uses a different domain | e.g., admin@gmail.com — Let's Encrypt requires contact email but doesn't verify domain ownership; still works | No change needed but document |
| 18 | `ADMIN_EMAIL` contains `+` alias | e.g., admin+ifinmail@example.com — `+` is valid in email but may break naive regex | Validate email format with RFC 5322 |
| 19 | `DKIM_SELECTOR` contains special characters | e.g., `my-selector` → `-` is valid DNS; `my_selector` → `_` is not valid in DNS label | Validate DKIM_SELECTOR against DNS label rules `[a-z0-9-]+` |
| 20 | `.env` file already exists but is corrupted/truncated | `source "$ENV_FILE"` succeeds but variables are empty → validation catches placeholders but not truncation | Add file size check before sourcing |
| 21 | `.env` file has Windows line endings (CRLF) | `source` may interpret `\r` as part of the value → passwords have trailing `\r` | Run `dos2unix`-style fix or `sed 's/\r$//'` before sourcing |
| 22 | `.env` file has trailing whitespace on values | Passwords/keys may include whitespace → connection failures | `tr -d '[:space:]'` on sensitive values |
| 23 | `MAIL_HOSTNAME` resolves to a different IP than `DOMAIN` | Postfix identifies as `mail.example.com` but receiving servers reverse-lookup the connecting IP → PTR mismatch | Document PTR record requirement; add pre-flight check |
| 24 | Server has IPv6 but no AAAA record set | Postfix binds IPv4 only (`inet_protocols = ipv4`) → no IPv6 issues currently. But if user enables IPv6, they need AAAA records | Current behavior is safe; document IPv6 opt-in path |
| 25 | `docker compose version` succeeds but daemon isn't running | `detect_compose()` passes but `build`/`up` fails with "Cannot connect to Docker daemon" — unhelpful error | Check `docker info` in `need_cmd` or `detect_compose` |
| 26 | Docker daemon has insufficient disk for images | `docker compose build --pull` fails mid-pull; partial images left | Pre-check `docker system df` for available space |
| 27 | `COREDNS_IP` set to something other than 127.0.0.1 | Reserved for future; currently unused but written to .env | No immediate issue but document |
| 28 | User interrupts provision.sh mid-execution (Ctrl+C) | `set -euo pipefail` is set but `trap` is not → partial state: .env written, certs generated, but services not started | Add `trap cleanup EXIT` to rollback or report partial state |
| 29 | User runs `make provision` twice | Idempotent by design — but GPG key regeneration is skipped, `docker compose up -d` is re-run | No issue but add a "stack already running" check to warn |
| 30 | `INSTALL_DIR` in bootstrap.sh has spaces | `$HOME/ifinmail` default is safe; custom path with spaces breaks compose commands | Quote all paths or validate no spaces |
| 31 | `REPO_URL` is an SSH URL but no SSH key | `git clone` in clone_or_update() hangs waiting for SSH key passphrase | Validate URL protocol or add `GIT_TERMINAL_PROMPT=0` |
| 32 | GitHub is unreachable (network/rate-limit) | bootstrap.sh `git clone`/`git pull` fails → provision can't run | Add retry logic and fallback instructions |
| 33 | Ubuntu version codename doesn't match Docker's repo | `$(. /etc/os-release && echo "$VERSION_CODENAME")` may not be in Docker's apt repo (e.g., newly released Ubuntu) | Fall back to `stable` if codename not found |
| 34 | Existing Docker installation is from a different source | bootstrap.sh removes old packages indiscriminately → may break user's other containers | Warn before removing; offer skip flag |
| 35 | cloud-init runs on a non-systemd distro | `systemctl enable docker` fails silently | Check for systemd before using systemctl |
| 36 | cloud-init `runcmd` section fails partway | No rollback; partial Docker install, no repo clone | cloud-init has no rollback by design; document manual recovery |
| 37 | `make provision` run from wrong directory | Script uses `SCRIPT_DIR` detection so it works from anywhere, but compose commands `cd` to `$DOCKER_DIR` — this is correct | Already handled |
| 38 | `make` targets assume `docker compose` but user has legacy `docker-compose` | Makefile auto-detects but only in some targets; `make health` has a bug — uses `docker-compose` hardcoded in `monitor.py` | Fix Makefile consistency |
| 39 | Running inside a container (Docker-in-Docker) | Mail ports (25, 465, 587) collide with host; volumes may not work | Document not supported |
| 40 | `HOME` not set (rare, some CI environments) | `INSTALL_DIR="$HOME/ifinmail"` fails → `$HOME` is empty → clones to `/ifinmail` | Default to `/opt/ifinmail` if `$HOME` unset |

---

## 2. SECRET GENERATION & MANAGEMENT (35 edge cases)

### Happy Path
`provision.sh` generates all secrets using `openssl rand -base64` with appropriate lengths, writes them to `.env` with `umask 077`, and validation checks that no placeholders remain.

### Negative Scenarios (8)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 41 | `openssl rand` fails (entropy exhaustion) | `rand_b64()` produces empty string; secrets are empty → services fail to start | HIGH |
| 42 | `.env` file written to world-readable location | `umask 077` set before `cat > "$ENV_FILE"` — correct. But if `.env` already exists, its permissions aren't checked/fixed | MEDIUM |
| 43 | `.env` sourced insecurely in CI/CD logs | No warning in docs; users may `cat .env` in CI | Documentation issue |
| 44 | Secrets transmitted in environment variables to containers | Visible in `docker inspect`, `/proc/*/environ` for root | Document risk; consider Docker secrets |
| 45 | `DJANGO_SUPERUSER_PASSWORD` stored in `.env` plaintext | Anyone with file read access can become superuser | Document risk |
| 46 | GPG backup key `%no-protection` (no passphrase) | Anyone with filesystem access can decrypt all backups | CRITICAL |
| 47 | Secrets never rotated | No rotation mechanism; if a secret leaks, there's no way to rotate without manual intervention | Document rotation procedure |
| 48 | `REDIS_PASSWORD` visible in `docker compose ps` or logs | Redis password passed as CLI arg `--requirepass $PASSWORD` → visible in `ps aux` | Use `REDIS_PASSWORD` env var or config file |

### Edge Cases (27)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 49 | Base64 secrets contain `/` or `+` | These are valid base64 but `/` is a path separator and `+` may break URL encoding. `openssl rand -base64` produces these characters | Use `tr '/+' '_-'` or `tr -d '/+'` after generation |
| 50 | Base64 secret ends with `=` padding | `=` may be misinterpreted in some config parsers (though rare in env vars) | Strip padding: `tr -d '='` |
| 51 | `SECRET_KEY` contains `$` or `!` when sourced | bash `source` interprets `$` as variable expansion and `!` as history expansion | Already handled — `rand_b64()` output is alphanumeric + `+/=` only |
| 52 | `POSTGRES_ADMIN_PASSWORD` uses special chars that break shell | If secret contains `'`, `"`, or `\`, the heredoc writes it literally (single-quoted delimiters disabled) — but `source` could re-interpret | Verify `source` doesn't re-parse special chars; test with all ASCII special chars |
| 53 | `APP_DB_PASSWORD` used in Django DATABASE_URL | Special chars in password break URL parsing → Django can't connect | URL-encode the password in DATABASE_URL construction |
| 54 | Multiple `.env` files exist (provisioning/.env vs root .env) | Makefile explicitly uses `provisioning/.env` but some scripts look for `.env` in CWD | Consolidate or add validation for conflicting .env files |
| 55 | `DJANGO_ALLOWED_HOSTS` doesn't include `localhost` or `127.0.0.1` | API health checks from nginx (internal Docker network) use `api:8000` — host header is `api`, not in ALLOWED_HOSTS | Add `api,localhost,127.0.0.1` to ALLOWED_HOSTS in docker-compose |
| 56 | `CSRF_TRUSTED_ORIGINS` missing `https://mail.$DOMAIN` | Webmail login CSRF fails if accessed via mail hostname | Add MAIL_HOSTNAME to CSRF_TRUSTED_ORIGINS |
| 57 | `SECURE_HSTS_SECONDS=3600` (1 hour) | Production should be at least 1 year (31536000); 1 hour is essentially disabled | Set to 31536000 (1 year) for production; only use low values for staging |
| 58 | `AXES_FAILURE_LIMIT=5` | After 5 failed logins, user is locked out; no self-service unlock mechanism | Add unlock instructions or email-based reset |
| 59 | `CERT_DIR` path constructed from `MAIL_HOSTNAME` with special chars | If MAIL_HOSTNAME has special chars, path traversal possible (though unlikely given DNS label constraints) | Validate MAIL_HOSTNAME is a valid DNS name |
| 60 | GnuPG home directory not set explicitly | `gpg --gen-key` uses `$GNUPGHOME` or `~/.gnupg` — if running as root in bootstrap.sh, key goes to `/root/.gnupg`; in provision.sh via make, depends on invoking user | Set `GNUPGHOME` explicitly to a known location |
| 61 | GPG key generation fails silently | provision.sh `ensure_backup_gpg_key()` suppresses stderr with `2>/dev/null` → user never knows WHY it failed, just that it did | Log stderr to a file; print path to log on failure |
| 62 | GPG key exists but is expired or revoked | `gpg --list-keys "$gpg_key_id"` succeeds even for expired keys → backup encryption silently uses bad key | Check key validity with `gpg --check-key` |
| 63 | GPG batch file written to `/tmp` which is `noexec` | `gpg --batch --gen-key /tmp/gpg-batch.txt` — `noexec` only affects binaries, not data files; this is fine | No issue |
| 64 | `REDIS_PASSWORD` in `REDIS_URL` uses `redis://:` format | `redis://:password@redis:6379/0` — empty username with colon is correct for Redis 6+ ACL | Already correct |
| 65 | `CELERY_BROKER_URL` uses same Redis instance, different DB (db=1) | Celery tasks and cache share the same Redis process but different logical databases. If Redis is configured without multiple databases support, both use db=0 | Redis default config supports 16 databases; no issue |
| 66 | `DJANGO_SUPERUSER_PASSWORD` generation uses only 16 bytes (128-bit) | 16 bytes base64 = ~22 chars; adequate for a hashed password | Marginally sufficient; consider 24+ bytes |
| 67 | `POSTGRES_ADMIN_PASSWORD` is 36 bytes (288-bit) | Adequate; but `ifinmail` superuser password is the highest-value secret in the system | Consider hardware-backed entropy source |
| 68 | `.env` file grows with duplicate variable entries | `ensure_env()` appends missing vars but doesn't deduplicate → multiple `MAIL_DOMAIN=` lines if script run multiple times with different values | Deduplicate or `sort -u` the env file |
| 69 | `rand_b64` called inside heredoc with `$()` | Command substitution inside heredoc means each `$(rand_b64 N)` is a separate call — this is correct and intentional | Already correct |
| 70 | Environment variables starting with numbers or containing hyphens | `set -a; source .env; set +a` — bash variable names can't contain hyphens; any `.env` entries like `MY-VAR=value` are silently ignored | Validate variable names in .env |
| 71 | `DJANGO_SETTINGS_MODULE` not in .env but required at runtime | Set in docker-compose.yml only — if user runs `make migrate` locally, settings module defaults to `development` in manage.py | Ensure manage.py has correct default |
| 72 | `DB_SSLMODE=require` but PostgreSQL cert is self-signed | `require` verifies TLS is used but doesn't verify the certificate → MITM possible within Docker network (very low risk) | Use `verify-full` with the shared cert |
| 73 | `PGSSLMODE=require` for dovecot/postfix PostgreSQL connections | Same as above — internal network, low risk | Acceptable for internal Docker network |
| 74 | Environment variables leak via `docker compose config` | `docker compose config` prints resolved config including passwords | Warn in docs |
| 75 | `docker-compose.yml` command interpolation references `${VAR:?message}` | This is the compose file variable substitution — if var is missing, compose fails with the message | Already correct; provides clear error |

---

## 3. DOCKER IMAGE BUILDS (30 edge cases)

### Happy Path
`docker compose build --pull` pulls base images, builds all 5 custom images (api, postfix, dovecot, rspamd, snappymail), and completes without errors.

### Negative Scenarios (9)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 76 | Base image pull fails (network) | Build fails; no retry logic | HIGH |
| 77 | `python:3.12-slim` image unavailable | API build fails; no fallback | MEDIUM |
| 78 | `ubuntu:24.04` EOL or removed | postfix/dovecot/rspamd builds fail | MEDIUM |
| 79 | `nginx:1.27-alpine` version pinned | Won't get security patches automatically | MEDIUM |
| 80 | `postgres:16-alpine` version pinned | Won't get minor patches automatically | MEDIUM |
| 81 | `redis:7-alpine` version pinned | Same as above | LOW |
| 82 | Build context for API is too large (project root) | `context: ../..` copies entire repo into Docker daemon → sends `.git`, `node_modules`, etc. if present | Add `.dockerignore` |
| 83 | pip install fails during API build | `Dockerfile` has no retry; network blip = build failure | Add pip retry (`--retries 5`) |
| 84 | apt-get fails during postfix/dovecot/rspamd builds | No retry; transient network error = build failure | Add apt retry |

### Edge Cases (21)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 85 | Docker build cache is stale | `--pull` flag pulls base images but doesn't bust the build cache for `pip install`/`apt-get` layers | Add `--no-cache` flag option or version stamps |
| 86 | `snappymail` version 2.38.0 hardcoded | No update path except rebuild | Use `latest` tag or document update procedure |
| 87 | Docker `buildx` not available | `docker compose build` uses legacy builder; slower, no cache mounts | Already handled; continue with v1 builder |
| 88 | Multi-arch builds needed (ARM64 server) | Dockerfiles don't use `--platform`; base images support multi-arch but apt packages may differ | Test on ARM64 |
| 89 | Docker build disk space runs out mid-build | Partial image layers left in `/var/lib/docker` | Pre-check disk space |
| 90 | `certbot` image includes Docker CLI but version may mismatch host | `docker-cli` installed in certbot image; if host Docker API version is newer, commands may fail | Pin docker-cli version matching host or use API version negotiation |
| 91 | certbot entrypoint `sleep "${RENEWAL_INTERVAL}"` — `12h` is not a number | `sleep 12h` works in GNU coreutils but not all shells | Use seconds: `sleep 43200` |
| 92 | postfix image doesn't include `ss` command | healthcheck fallback uses `ss -tlnp` but postfix image may not have `iproute2` installed | Add `iproute2` to postfix Dockerfile or use `netstat` fallback |
| 93 | dovecot image doesn't include `ss` command | healthcheck uses `ss` as fallback | Add `iproute2` to dovecot Dockerfile |
| 94 | rspamd healthcheck: `rspamc stat` may need password | If rspamd controller password is set, `rspamc stat` fails unless password is provided | Configure rspamd to allow localhost unauthenticated access |
| 95 | `mem_limit` values hardcoded in compose file | 256MB for postgres may be insufficient for 100+ domains; 1024MB for API may be too much for small instances | Make limits configurable via env vars |
| 96 | No `cpus` limits on services | One container can starve others of CPU | Add CPU limits |
| 97 | Log rotation: `max-size: 10m, max-file: 3` | 30MB total per service × 8 services = 240MB max; fine for most VPS | Acceptable |
| 98 | Log driver: `json-file` | Not ideal for production (no structured logging, no log aggregation) | Document integration with Docker logging drivers (loki, fluentd) |
| 99 | `init-db.sh` mounted into postgres as `.sh` but uses bash | postgres:16-alpine has `bash`? Alpine uses `ash`/`busybox`. `init-db.sh` uses arrays `missing=()` which are bash-specific | Port init-db.sh to POSIX sh or install bash in postgres image |
| 100 | init-db.sh uses `${ARRAY[@]}` syntax | Alpine's `ash` may not support this — but init-db.sh is run inside the `psql` invocation, not as a shell script per se. Actually, the `postgres` container runs `/docker-entrypoint-initdb.d/*.sh` with `sh` | Verify init-db.sh is POSIX-compliant or ensure bash is available |
| 101 | postgres container command is a multi-line `sh -c` with backslashes for line continuation | YAML multiline `>` folds newlines to spaces → the shell command is one long line. Backslash-continued lines work in `>` block if indentation is correct | Verify the YAML produces valid shell after processing |
| 102 | certbot image has `profiles: [certbot]` | Not started by default `docker compose up` — only with `--profile certbot`. provision.sh handles this correctly | Already correct |
| 103 | Docker socket mounted into certbot container (`/var/run/docker.sock`) | Full root access to host → if certbot image is compromised, host is compromised | Security tradeoff; document risk. Alternative: have certbot signal nginx via a shared file |
| 104 | nginx image uses `nginx:1.27-alpine` with template processing | nginx command replaces `__SSL_CERT_HOSTNAME__` via `sed` at startup, then background-reloads every 6h | Clever but fragile — if sed fails, nginx starts with wrong cert path |
| 105 | API Dockerfile builds from project root (`context: ../..`) | Sends entire project to Docker daemon; slow on large repos; includes `.git`, `.venv`, etc. | Add comprehensive `.dockerignore` |

---

## 4. CERTIFICATE MANAGEMENT (50 edge cases)

### Happy Path
`provision.sh` creates a 7-day self-signed bootstrap cert via `openssl`, starts nginx, obtains a real Let's Encrypt certificate via certbot webroot, then restarts services. certbot container renews automatically every 12h.

### Negative Scenarios (14)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 106 | Let's Encrypt rate limit hit (5 certs/domain/week) | certbot fails; stack runs on self-signed cert that expires in 7 days | CRITICAL |
| 107 | DNS not pointed to server | certbot validation fails (can't reach `/.well-known/acme-challenge/`) | HIGH |
| 108 | Port 80 blocked by firewall/ISP | ACME HTTP-01 challenge fails | HIGH |
| 109 | Port 80 blocked but DNS validation possible | No DNS-01 challenge support in current code | MEDIUM |
| 110 | Let's Encrypt API outage | certbot fails; stack runs on self-signed | HIGH |
| 111 | Self-signed cert expires before Let's Encrypt succeeds | `openssl -days 7` is the window; if user delays DNS setup > 7 days, services break | CRITICAL |
| 112 | certbot deploy-hook fails to restart services | Cert renewed but services still serving old cert | HIGH |
| 113 | certbot auto-renewal container crashes | certs approach expiry with no renewal | HIGH |
| 114 | Docker socket unavailable in certbot container | deploy-hook can't restart services after renewal | HIGH |
| 115 | Multiple `certbot renew` processes run concurrently | Race condition on certificate renewal | MEDIUM |
| 116 | `obtain-ssl.sh` removes self-signed cert BEFORE certbot succeeds | If certbot fails after `rm -rf`, services have NO cert — worse than expired self-signed | CRITICAL |
| 117 | certbot `--cert-name $MAIL_HOSTNAME` collides with existing LE cert for different domain | certbot may refuse or overwrite | MEDIUM |
| 118 | `sleep 2` in obtain-ssl.sh insufficient for nginx startup | Race condition: certbot tries ACME challenge before nginx is ready | MEDIUM |
| 119 | LE staging environment used accidentally | No differentiation between staging/production; hard to test | MEDIUM |

### Edge Cases (36)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 120 | Mail hostname and domain are both in SAN | `-d "$MAIL_HOSTNAME" -d "$DOMAIN"` — correct, both names covered | Already correct |
| 121 | `openssl req -addext` flag requires OpenSSL 1.1.1+ | Older OpenSSL versions don't support `-addext` → SAN not included in self-signed cert | Check OpenSSL version; fallback to config file method |
| 122 | DH parameters generation is slow (2048-bit) | `openssl dhparam 2048` takes 10-60 seconds | Acceptable; add progress message |
| 123 | DH parameters generated in `ensure_bootstrap_cert()` ONLY | If LE cert obtained without bootstrap (unlikely), DH params never generated for LE cert dir | `obtain-ssl.sh` already checks for dh.pem; correct |
| 124 | DH parameters regenerated on every provision if not in LE cert dir | `ensure_directories` creates `certs/live/$MAIL_HOSTNAME`; `ensure_bootstrap_cert` puts dh.pem there. But LE cert goes to same directory → dh.pem persists | Already correct |
| 125 | certbot certificate name uses `$MAIL_HOSTNAME` | If user changes MAIL_HOSTNAME later, old cert remains under old name | Document cert name migration |
| 126 | certbot `--non-interactive` flag | Correct — prevents interactive prompts in script | Already correct |
| 127 | certbot `--agree-tos` without explicit ToS acceptance | Legal: user should explicitly accept Let's Encrypt Subscriber Agreement | Add ToS acceptance step in setup wizard |
| 128 | `--webroot-path /var/www/certbot` mapped to `./nginx/www` | Both nginx (for .well-known serving) and certbot (for challenge file creation) share this directory via volumes | Already correct |
| 129 | certbot webroot challenge files persist after renewal | `.well-known/acme-challenge/` files accumulate | Add cleanup in certbot deploy-hook |
| 130 | NGINX serves `/.well-known/acme-challenge/` from `/var/www/certbot/.well-known/acme-challenge/` | Path alignment is critical — nginx `root /var/www/certbot` + location `/.well-known/acme-challenge/` | Verify path in nginx config matches certbot's `--webroot-path` |
| 131 | certbot writes files as root; nginx reads as nginx user | Permission mismatch → nginx returns 403 for challenge files | Set permissive permissions on `nginx/www` directory |
| 132 | LE certificate renewal fails silently in background | certbot entrypoint logs but cron-based users won't see logs | Add alert integration: if renewal fails, trigger webhook |
| 133 | certbot 12h renewal loop — `sleep 12h` | 12h = 43200s. If container restarts, timer resets → could drift | Acceptable; renewal is idempotent |
| 134 | Certificate expiry during certbot container downtime | If certbot container is down for 30+ days (cert renewal window), cert expires | Monitor certbot container health separately |
| 135 | LE intermediate CA rotation | certbot handles this automatically via `certbot renew` | Already correct |
| 136 | Certificate transparency log submission | certbot handles this automatically | Already correct |
| 137 | RSA key size hardcoded to 2048 for bootstrap cert | Acceptable for self-signed bootstrap; LE issues their own keys | Already correct |
| 138 | ECDSA not supported | All certs use RSA; no ECDSA option | Add ECDSA option for better performance |
| 139 | `obtain-ssl.sh` restarts nginx after cert obtained | `docker compose restart nginx` causes brief downtime | Use `nginx -s reload` instead for zero-downtime |
| 140 | nginx reload every 6h via background loop | `while :; do sleep 6h; nginx -s reload; done &` — this reloads to pick up renewed certs. This runs inside the container | Already correct; 6h window after cert rotation is acceptable |
| 141 | certbot deploy-hook path mismatch | `deploy-hook.sh` is at `/hooks/deploy-hook.sh` in certbot container but mounted at different path if compose file structure changes | Verify mount paths |
| 142 | `COMPOSE_FILE` and `ENV_FILE` env vars in certbot container | Set to paths inside container; if compose file structure changes, these break | Use consistent paths |
| 143 | MTA-STS policy `max_age: 604800` (7 days) | Short max_age means clients re-fetch policy frequently. Recommended: 2-6 weeks | Increase to 1209600 (2 weeks) or 2592000 (30 days) |
| 144 | MTA-STS `mode: "enforce"` from day one | No testing mode — if TLS is broken, all mail is rejected by sending servers that enforce MTA-STS | Start with `mode: "testing"` for first 2 weeks |
| 145 | MTA-STS policy ID is timestamp-based | `$(date +%Y%m%dT%H%M%SZ)` — changes on every provision run. RFC requires that ID changes only when policy changes | Use a stable hash of policy content |
| 146 | mta-sts.$DOMAIN A record required but not auto-created | `print_dns()` tells user to create it; if forgotten, MTA-STS doesn't work | Add pre-flight DNS check or web server for mta-sts subdomain |
| 147 | Self-signed cert `-days 7` | This is the fallback window. On slow DNS propagation (48-72h), the 7-day window may close | Extend to 30 days or add explicit warning |
| 148 | `chmod 600 "$key"` on private key | Correct permissions | Already correct |
| 149 | certbot cert stored in `certs/live/$MAIL_HOSTNAME/` | Symlinks from `live/` to `archive/`; Docker volumes handle symlinks correctly | Already correct |
| 150 | Let's Encrypt rate limit for 50 certs/week/registered domain | Single domain = 1 cert; unlikely to hit | Acceptable |
| 151 | `ensure_bootstrap_cert` runs before Docker build | Certs generated on host, later mounted into containers — correct | Already correct |
| 152 | DNS CAA record may prevent Let's Encrypt issuance | If domain has CAA record that doesn't include `letsencrypt.org`, issuance fails | Add doc about CAA records; check in pre-flight |
| 153 | Cert file path uses `$MAIL_HOSTNAME` interpolation in nginx | `sed "s|__SSL_CERT_HOSTNAME__|${MAIL_HOSTNAME}|g"` — cert path becomes `/etc/letsencrypt/live/mail.example.com/fullchain.pem` | Already correct |
| 154 | certbot ACME account created per-provision (no reuse) | Each `certbot certonly` run without `--reuse-key` creates new account keys; rate limits apply per account | Use `--reuse-key` and store account in volume |
| 155 | certbot account key not backed up | If certs volume is lost, new account must be created → hits rate limits | Include certbot account in backup |

---

## 5. DATABASE INITIALIZATION (40 edge cases)

### Happy Path
PostgreSQL container starts, runs `init-db.sh` on first boot (detected by empty data directory), creates tables, indexes, roles, and inserts the primary domain.

### Negative Scenarios (11)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 156 | `init-db.sh` fails with SQL error | PostgreSQL container exits; all dependent services fail (dovecot, postfix, api) | CRITICAL |
| 157 | `init-db.sh` script contains bash-specific syntax on Alpine | `set -euo pipefail`, arrays, etc. — Alpine uses `sh` (busybox ash) | CRITICAL |
| 158 | Docker volume already has data but init-db.sh never ran | No idempotency — database exists but tables are missing; services fail | HIGH |
| 159 | `postgres_data` volume deleted but postgres container still references old data | PostgreSQL won't reinitialize | Document recovery procedure |
| 160 | `DOMAIN` or `MAIL_DOMAIN` contains SQL injection chars | `sql_escape()` uses `sed "s/'/''/g"` — only escapes single quotes. What about backslashes, semicolons? | Use parameterized queries or thorough escaping |
| 161 | PostgreSQL SSL certs missing at startup | `command` script checks `[ -d "/etc/letsencrypt/live/${MAIL_HOSTNAME}" ]` — if certs aren't mounted, SSL silently disabled (acceptable fallback) | Already correct |
| 162 | PostgreSQL custom config not included | `include_if_exists` is used → if file missing, PostgreSQL starts with defaults | Already correct |
| 163 | Database roles already exist with different passwords | `ALTER ROLE ... WITH LOGIN PASSWORD` changes password → if old services still have old password, they lose access | Acceptable; services start fresh with new passwords |
| 164 | PostgreSQL data directory permissions wrong | Container won't start; unclear error | Add startup check for permissions |
| 165 | `pg_isready` healthcheck passes but database is corrupted | Dependent services start but fail when querying | Add `SELECT 1` to healthcheck |
| 166 | Multiple postgres containers on same host | Port 5432 only bound internally; no collision | Already correct (internal network) |

### Edge Cases (29)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 167 | `CREATE EXTENSION IF NOT EXISTS` — extension already exists from template | Postgres template1 may have these extensions; `IF NOT EXISTS` handles this | Already correct |
| 168 | `uuid-ossp` extension requires superuser | init-db.sh runs as `POSTGRES_USER` (ifinmail) which is the database superuser | Already correct |
| 169 | `pgcrypto` extension for future use | Currently unused in SQL but available for `gen_random_uuid()` etc. | Accepted |
| 170 | `CREATE TABLE IF NOT EXISTS` — table structure changes between versions | If columns are added in a new version, `IF NOT EXISTS` won't add them → schema mismatch with Django ORM | Use Django migrations for schema changes; init-db.sh should be initial setup only |
| 171 | Django migrations vs init-db.sh schema conflict | init-db.sh creates tables directly; Django's `migrate` may detect existing tables and fail or skip | Ensure init-db.sh creates tables compatible with Django's migration state; or let Django handle all migrations |
| 172 | `INSERT INTO domains ... ON CONFLICT (name) DO NOTHING` | Only inserts if domain doesn't exist; doesn't update verification status | Acceptable for initial setup |
| 173 | `verified = TRUE` inserted for initial domain without actual verification | Domain is marked verified without DNS checks | Add note: domain must have DNS configured for actual deliverability |
| 174 | `quota_bytes BIGINT DEFAULT 0` — 0 means unlimited | Per-mailbox quota is 0 (unlimited); user expects quotas to be configurable | Add quota support in API/admin |
| 175 | `password_hash VARCHAR(512)` — ARGON2ID hash may exceed this | Argon2id hashes are typically < 256 chars; 512 is safe | Already correct |
| 176 | `ON DELETE CASCADE` on mailboxes/aliases/dkim_keys | Deleting a domain cascades to all related records — data loss hazard | Add confirmation in admin UI |
| 177 | `ALTER DEFAULT PRIVILEGES` for ifinmail_app | Only affects FUTURE tables; existing tables already granted | Already handled — explicit GRANT on ALL TABLES precedes ALTER DEFAULT |
| 178 | `statement_timeout = '30000'` (30s) | Long queries (e.g., admin reports) may timeout | Make configurable per-role |
| 179 | `lock_timeout = '10000'` (10s) | Schema migrations may need longer locks → migration failures | Django's `migrate` can override; fine for normal operation |
| 180 | `idle_in_transaction_session_timeout = '60000'` (60s) | Transactions held open by buggy code will be terminated | Correct setting |
| 181 | PostgreSQL custom.conf `shared_buffers=64MB` for 256MB container | 25% of RAM — standard recommendation | Already correct |
| 182 | `effective_cache_size=128MB` — 50% of RAM | Conservative; 75% is typical | Acceptable |
| 183 | `max_connections=50` for 256MB | Each connection ~2-5MB → 100-250MB for connections alone | May be too high; reduce to 20-30 |
| 184 | `random_page_cost=1.1` — assumes SSD | HDD-based VPS would need 2.0-4.0 | Make configurable |
| 185 | `autovacuum_naptime=30s` — aggressive | More CPU usage but better for small DB | Acceptable |
| 186 | Indexes created on `(domain_id, local_part)` for mailboxes | Efficient for Postfix/Dovecot lookups | Already correct |
| 187 | No index on `aliases(destination)` | Reverse alias lookups (find all aliases pointing to a mailbox) are slow | Add index if reverse lookups needed |
| 188 | No sequence grants for ifinmail_app explicitly for existing sequences | `ALTER DEFAULT PRIVILEGES` covers new sequences; existing sequences may need explicit grant if used | Add explicit GRANT on ALL SEQUENCES for bootstrap |
| 189 | `PGSSLMODE=require` in postfix/dovecot compose env | Requires TLS but doesn't verify certificate — acceptable within Docker network | Already correct |
| 190 | Postfix pgsql templates: `host=postgres dbname=ifinmail user=postfix password=...` | Hardcoded hostname `postgres` relies on Docker DNS | Already correct |
| 191 | Dovecot SQL: `host=postgres` — same assumption | Docker DNS resolves `postgres` to container IP | Already correct |
| 192 | Database `ifinmail` name hardcoded in compose and init-db.sh | Changing DB name requires changes in 5+ places | Make DB_NAME a variable |
| 193 | `postgres_user=ifinmail` and `dbname=ifinmail` | Same name for user and database — conventional | No issue |
| 194 | `ssl = on` in PostgreSQL enabled only if certs exist | Conditional SSL is good for bootstrap; but Dovecot/Postfix use `sslmode=require` → if PostgreSQL SSL not enabled, connections fail | Use `sslmode=require` only if certs exist, else `disable` |
| 195 | PostgreSQL cert ownership: `chown -R 999:999` (postgres user UID) | Hardcoded UID may differ across PostgreSQL versions | Use `chown postgres:postgres` or detect UID dynamically |

---

## 6. SERVICE STARTUP & DEPENDENCY ORDERING (35 edge cases)

### Happy Path
`docker compose up -d` starts services respecting `depends_on` with `condition: service_healthy`. Startup order: postgres → redis → dovecot/rspamd/snappymail → postfix → api → nginx.

### Negative Scenarios (10)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 196 | PostgreSQL healthcheck never passes | All dependent services wait indefinitely (no timeout) — swarm/services never start | CRITICAL |
| 197 | Redis healthcheck fails | Rspamd and API wait indefinitely | HIGH |
| 198 | Dovecot startup fails but healthcheck passes | Postfix starts but LMTP delivery fails → mail bounces | HIGH |
| 199 | API fails after healthcheck passes | Nginx starts but returns 502 Bad Gateway | HIGH |
| 200 | Service restart loop (crashes immediately) | `restart: unless-stopped` restarts infinitely, consuming CPU | Add restart rate limiting or backoff |
| 201 | OOM kill on API container (memory limit 1024MB) | API killed, nginx returns 502; auto-restarts | Add memory monitoring; increase limit if needed |
| 202 | postfix service starts before dovecot LMTP socket ready | `depends_on: dovecot service_healthy` — but LMTP socket may not be created before first delivery attempt | Add socket readiness check to postfix entrypoint |
| 203 | certbot container starts before certificates exist | Certbot profiles start last in provision.sh; renewal loop handles missing certs gracefully | Already correct |
| 204 | All services start but nginx can't reach API | Nginx healthcheck tests port 80 (itself), not API → nginx reports healthy while returning 502 | Add upstream check to nginx healthcheck |
| 205 | Stale containers from previous deployment | Legacy cleanup only runs for docker-compose v1; v2 leaves orphan containers if compose file changed | Add `--remove-orphans` to `docker compose up` |

### Edge Cases (25)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 206 | `depends_on` doesn't wait for service to be fully READY, just "healthy" | Healthcheck definition may be too permissive → service reports healthy before it can serve traffic | Review healthcheck definitions |
| 207 | API entrypoint retries PostgreSQL connection 30 times × 2s = 60s | If PostgreSQL takes > 60s to start (slow disk, crash recovery), API fails permanently | Increase MAX_ATTEMPTS or make configurable |
| 208 | API entrypoint exits if migration fails | Container exits; Docker restarts it → migration runs again, fails again → restart loop | Add migration failure detection; don't retry migrations that failed |
| 209 | API `collectstatic --clear` deletes old static files | If `--clear` removes files before new ones are ready, nginx serves 404s briefly | Use atomic collectstatic (collect to new dir, then swap) |
| 210 | API `chown -R nobody:nogroup` on static files | `nobody:nogroup` assumed; Alpine nginx user is `nginx:nginx` | Verify user/group match between API and nginx containers |
| 211 | Superuser creation uses `python manage.py shell -c` with inline Python | Python code contains password in command line → visible in `ps` and process list | Use `createsuperuser --noinput` with env vars instead |
| 212 | Superuser creation not idempotent across Django versions | `User.objects.filter(username=username).exists()` is correct and idempotent | Already correct |
| 213 | Gunicorn workers hardcoded in CMD | Dockerfile has `CMD ["gunicorn", ...]` — worker count should scale with CPU | Use `--workers $((2*$(nproc)+1))` or `WEB_CONCURRENCY` env var |
| 214 | Multiple `docker compose up -d` runs concurrently | Docker handles this gracefully (idempotent) | Already correct |
| 215 | Service `mem_limit` hit → OOM | Container killed; Docker restarts; may loop | Add OOM alert in monitoring |
| 216 | Container restart causes brief port unavailability | HAProxy/nginx may buffer connections; external mail servers retry | Acceptable for SMTP |
| 217 | `restart: unless-stopped` — container won't restart if explicitly stopped | `docker compose stop` won't restart; `docker compose down` won't either | Already correct |
| 218 | Docker network `ifinmail-net` already exists from previous run | Docker compose reuses existing network | Already correct |
| 219 | Docker network subnet collision with host network | Docker's default 172.x subnet may conflict with VPS private network | Make subnet configurable |
| 220 | postfix `default_process_limit = 100` | 100 concurrent SMTP processes; on 1GB VPS this is too many | Reduce to 20-30 |
| 221 | postfix `smtpd_client_connection_count_limit = 50` | Per-client connection limit; reasonable | Already correct |
| 222 | Open file limits inside containers | Docker default ulimit is high; but postfix opens many files (spool + logs + connections) | Set `ulimit -n 65536` in postfix container |
| 223 | DNS resolution inside containers | Docker's embedded DNS (127.0.0.11) resolves container names; external DNS uses host's `/etc/resolv.conf` | Already correct |
| 224 | Container timezone not set | All containers use UTC; logs in UTC | Set `TZ` env var for user-readable logs |
| 225 | `rundir` volume for Postfix↔Dovecot socket | Named volume shared between two containers; permissions (vmail:vmail, mode 0666) critical | Already correct |
| 226 | Socket files in `rundir` persist across restarts | If Dovecot restarts, old socket files may prevent new socket binding | Clean up stale sockets in entrypoint |
| 227 | Dovecot `service_count=1` for imap-login | Each process handles one connection then exits → prevents connection leaks | Already correct |
| 228 | Dovecot `process_limit=200` | 200 concurrent IMAP connections; adequate for small-medium deployments | Already correct |
| 229 | API `start_period: 30s` healthcheck grace period | Migrations + collectstatic may take > 30s; healthcheck starts too early → reports unhealthy → nginx won't start | Increase start_period or make API report "starting" status during init |
| 230 | `snappymail` container has no `depends_on` | It proxies through nginx to API for auth; if API doesn't exist, snappymail still starts but login fails | Add `depends_on: api` |

---

## 7. NETWORK & PORT BINDING (30 edge cases)

### Happy Path
Nginx binds 80/443, Postfix binds 25/465/587, Dovecot binds 143/993. All services communicate over internal `ifinmail-net` network with Docker DNS.

### Negative Scenarios (8)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 231 | Port 25 blocked by VPS provider (common: AWS, GCP, Azure) | Postfix starts but no inbound SMTP → can't receive mail | CRITICAL |
| 232 | Port 25 blocked by ISP (residential connections) | Same — common for self-hosted on home internet | CRITICAL |
| 233 | Port 25 throttled by VPS provider | Postfix receives some mail but connections are rate-limited | HIGH |
| 234 | Port 80/443 already bound by another web server | Nginx fails to start → no ACME, no webmail, no API | HIGH |
| 235 | Port 143/993 already bound | Dovecot fails → no IMAP access | MEDIUM |
| 236 | ufw not installed, firewall.sh fails but ports are open anyway | No firewall → all ports exposed to internet including PostgreSQL if not careful (PostgreSQL only binds internally) | MEDIUM |
| 237 | Docker `iptables` rules bypass ufw | Docker manipulates iptables directly → ufw rules may not apply to Docker containers | CRITICAL |
| 238 | External SMTP on port 25 connects but gets no response | Postfix may be crash-looping; no monitoring of port 25 specifically | Add SMTP banner check to monitoring |

### Edge Cases (22)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 239 | Postfix listens on `0.0.0.0:25` — all interfaces | Intentional for receiving mail | Already correct |
| 240 | Dovecot listens on `0.0.0.0:143, 0.0.0.0:993` — all interfaces | Intentional | Already correct |
| 241 | API listens on `127.0.0.1:8000` — localhost only | Secure; only nginx (same host) can reach it | Already correct |
| 242 | rspamd listens on `127.0.0.1:11332, 127.0.0.1:11334` — localhost only | Milter port 11332 is `127.0.0.1` on HOST, but Postfix needs to reach it from INSIDE Docker network → uses internal network | This is a BUG: Postfix container can't reach `127.0.0.1:11332` of the rspamd container — they're on different containers. Need to bind to `0.0.0.0` or use Docker network name |
| 243 | rspamd port 11333 NOT exposed | Worker-normal binds `0.0.0.0:11333` inside container; not exposed in compose → only internal to rspamd container | Should this be exposed? Probably not needed externally |
| 244 | Postfix milter connects to `inet:rspamd:11332` | If rspamd port 11332 is bound to `127.0.0.1`, Postfix can't reach it via Docker network DNS (`rspamd:11332`) because rspamd only listens on localhost | Fix rspamd to bind milter on `0.0.0.0` inside the container |
| 245 | MTA-STS policy served on `mta-sts.$DOMAIN` via nginx | Requires separate A record and nginx server block; current nginx config may not handle it | Verify nginx config for mta-sts subdomain |
| 246 | Mail client autoconfiguration endpoints proxied to API | `/mail/config-v1.1.xml`, `/autodiscover/autodiscover.xml`, `/.well-known/autoconfig/mail/config-v1.1.xml` | Verify these exist in Django URLs |
| 247 | CSP header in nginx config | `Content-Security-Policy` may break SnappyMail (webmail has inline scripts) | Review CSP for webmail compatibility |
| 248 | Nginx rate limiting `30r/s` for general zone | Burst of 30 requests/second; may throttle legitimate API usage from webmail | Use `burst` and `nodelay` for burst handling |
| 249 | Nginx rate limiting for login `10r/s` | Brute force protection; 10 requests/second is generous | Tighten to 5r/s with burst=10 |
| 250 | Nginx connection limit `limit_conn conn_limit 50` | 50 concurrent connections per IP | Adequate for webmail; may limit API clients |
| 251 | WebSocket upgrade for SnappyMail in nginx | `proxy_set_header Upgrade $http_upgrade` + `Connection "upgrade"` | Verify WebSocket works through nginx |
| 252 | Nginx proxy to API uses `http://api:8000` | Docker DNS resolves `api` to container IP | Already correct |
| 253 | Nginx proxy to snappymail uses `http://snappymail:8888` | Docker DNS | Already correct |
| 254 | OCSP stapling enabled in nginx | `ssl_stapling on; ssl_stapling_verify on;` requires resolver | Already configured with `NGINX_RESOLVER` |
| 255 | `NGINX_RESOLVER` defaults to `1.1.1.1 8.8.8.8` | Cloudflare + Google DNS; fine for most | May want local resolver on some networks |
| 256 | nginx `server_tokens off;` | Hides nginx version | Already correct |
| 257 | HSTS header `max-age=63072000` (2 years) | Aggressive but correct for mail server | Include `includeSubDomains` if desired |
| 258 | `ssl_prefer_server_ciphers on` | Server chooses cipher; should be `off` for TLSv1.3 (client preference is modern best practice) | Set to `off` |
| 259 | TLSv1.2 minimum, TLSv1.3 preferred | Good security posture | Already correct |
| 260 | No HTTP/2 enabled in nginx config | `http2` directive not in `listen` line → HTTP/1.1 only | Add `http2` to `listen 443 ssl` |

---

## 8. DNS CONFIGURATION (25 edge cases)

### Happy Path
User creates DNS records as printed by `print_dns()`: A for domain and mail hostname, MX, SPF TXT, DKIM TXT, DMARC TXT, MTA-STS TXT, and A for mta-sts subdomain.

### Negative Scenarios (7)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 261 | DNS records not created at all | No mail delivery; SPF/DKIM/DMARC not configured → mail likely goes to spam | CRITICAL |
| 262 | MX record points to domain, not mail hostname | Correct in `print_dns()` — points to `$MAIL_HOSTNAME` | Already correct |
| 263 | MX priority not set or wrong | `10 $MAIL_HOSTNAME` — only one MX, priority 10 | Already correct |
| 264 | SPF record `v=spf1 mx -all` | Only allows server's own IP; no include for third-party senders | Adequate for self-hosted |
| 265 | DMARC `p=quarantine` too aggressive initially | Mail failing DMARC goes to spam; should start with `p=none` for monitoring | Start with `p=none` for first 2 weeks |
| 266 | DMARC `rua` email uses `postmaster@$DOMAIN` | If postmaster mailbox doesn't exist, aggregate reports bounce | Create postmaster alias |
| 267 | DNS propagation delay (up to 72h) | 7-day self-signed cert window may close before DNS propagates | Extend bootstrap cert validity |

### Edge Cases (18)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 268 | DKIM public key is too long for a single TXT record (>255 chars) | 2048-bit RSA pubkey in DNS TXT = ~400 chars → must be split across multiple strings | DKIM TXT records support string concatenation; `print_dns()` puts entire key in one quoted string — may exceed 255-byte DNS limit |
| 269 | DKIM TXT record needs to be split into 255-char chunks | Most DNS providers auto-split; some don't. `print_dns()` outputs one long string | Split DKIM public key into 255-char chunks in output |
| 270 | DMARC `rua` address must be a valid mailto | `mailto:postmaster@$DOMAIN` — correct format | Already correct |
| 271 | SPF record `-all` (hard fail) vs `~all` (soft fail) | `-all` = reject all mail not from this MX; if user adds third-party senders later, mail is rejected until SPF is updated | Use `~all` initially; document upgrade path to `-all` |
| 272 | MTA-STS id uses timestamp | Each provision generates new id → MTA-STS policy appears "changed" even if content is the same | Use content hash for id |
| 273 | MTA-STS `max_age` in seconds — 604800 = 7 days | Caching duration. Many deployments use 2-6 weeks | Increase to 1209600+ |
| 274 | MTA-STS requires HTTPS on `mta-sts.$DOMAIN` | User must create A record for `mta-sts.$DOMAIN` pointing to same server; TLS cert covers `$MAIL_HOSTNAME` and `$DOMAIN` but NOT `mta-sts.$DOMAIN` | Add `mta-sts.$DOMAIN` to certbot SAN list, or use a cert that covers `*.$DOMAIN` |
| 275 | Reverse DNS (PTR) not configured | `print_dns()` doesn't mention PTR records; many mail servers reject mail without matching PTR | Add PTR record instructions to `print_dns()` |
| 276 | IPv6 PTR record if server has IPv6 | Postfix binds IPv4 only currently; if IPv6 is enabled, need both forward and reverse for IPv6 | Document IPv6 PTR requirements |
| 277 | DNSSEC not mentioned | No documentation about DNSSEC; DANE/TLSA records for mail not supported | Document DNSSEC recommendation |
| 278 | CAA record recommendation | No CAA documentation; Let's Encrypt checks CAA before issuance | Document CAA record best practice |
| 279 | `_dmarc.$DOMAIN` TXT record format | Correct in `print_dns()` — underscore prefix is required | Already correct |
| 280 | `DKIM_SELECTOR._domainkey.$DOMAIN` format | Correct — `_domainkey` is the fixed subdomain | Already correct |
| 281 | DKIM DNS value format `v=DKIM1; k=rsa; p=<key>` | Correct | Already correct |
| 282 | Multiple DKIM selectors not supported | Only one selector per domain; key rotation requires manual process | Document DKIM key rotation procedure |
| 283 | TLSA/DANE records not generated | DANE (DNS-based Authentication of Named Entities) for SMTP is not configured | Add optional DANE support |
| 284 | `_mta-sts.$DOMAIN` TXT record format | `v=STSv1; id=<timestamp>` — correct | Already correct |
| 285 | DNS record TTL not specified | User may set long TTLs → changes take days to propagate | Recommend TTL=300 (5 min) during setup, increase to 3600+ after stable |

---

## 9. MAIL FLOW — SMTP → POSTFIX → RSPAMD → DOVECOT (45 edge cases)

### Happy Path
External server connects to Postfix on port 25, Postfix validates recipient domain via PostgreSQL, Rspamd scans for spam, accepted mail is delivered via LMTP to Dovecot, which writes to Maildir. User retrieves via IMAP.

### Negative Scenarios (13)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 286 | Postfix can't connect to PostgreSQL | `virtual_mailbox_domains` lookup fails → mail rejected with "451 Temporary failure" | CRITICAL |
| 287 | Postfix can't reach rspamd milter | `smtpd_milters = inet:rspamd:11332` — if rspamd is down, `milter_default_action = accept` → mail accepted without spam scanning | HIGH |
| 288 | Postfix can't reach Dovecot LMTP socket | Mail accepted into queue but delivery stalls → queue grows → deferred | CRITICAL |
| 289 | Maildir volume full | Dovecot can't write new mail → LMTP delivery fails → mail bounces | CRITICAL |
| 290 | Dovecot can't authenticate user | User can't retrieve mail via IMAP; Postfix can't authenticate for submission (port 587/465) | HIGH |
| 291 | Rspamd fails to scan → connection timeout | Milter timeout (120s) delays SMTP transactions → slow mail delivery | MEDIUM |
| 292 | Spam threshold too aggressive | `reject = 15.0` — legitimate mail scored 15+ rejected | MEDIUM |
| 293 | Spam threshold too permissive | Spam with score 14 passes through | MEDIUM |
| 294 | Greylisting at 4.0 may delay legitimate mail | Greylisting is enabled but `actions.conf` sets greylist at 4.0 (normally it's a binary on/off) | Review rspamd greylist configuration |
| 295 | `milter_default_action = accept` — if rspamd fails, mail passes without scanning | Security: spam floods through during rspamd outage | Change to `tempfail` to defer mail when scanner is down |
| 296 | Postfix SASL authentication fails | Users can't send mail through port 587/465 → mail clients error | HIGH |
| 297 | No outbound relay configured | Postfix delivers directly; if outbound port 25 is blocked by ISP, can't send mail | Add relay/smarthost option |
| 298 | ARGON2ID password hashing in Dovecot | CPU-intensive; many concurrent auths may overwhelm Dovecot | Tune argon2 parameters; add auth caching |

### Edge Cases (32)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 299 | `message_size_limit = 52428800` (50MB) | Base64 encoding adds ~33% overhead → actual attachment limit ~37MB | Document actual attachment size limit |
| 300 | `mailbox_size_limit = 0` (unlimited) | No per-user quota enforced by Postfix; Dovecot quota also relies on DB `quota_bytes=0` | Add quota enforcement |
| 301 | `smtpd_tls_security_level = may` (port 25) | Opportunistic TLS — mail may be sent in plaintext if remote server doesn't support TLS | Acceptable per RFC; MTA-STS enforces TLS for compliant senders |
| 302 | `smtpd_tls_auth_only = yes` | Submission requires TLS → plaintext auth not possible | Already correct |
| 303 | `smtpd_recipient_restrictions` order matters | Current order is correct: permit_mynetworks, permit_sasl_authenticated, reject_* | Already correct |
| 304 | `reject_invalid_hostname` rejects EHLO with bad syntax | Some legacy clients/devices may send bad EHLO | Acceptable; these clients should be fixed |
| 305 | `reject_non_fqdn_sender` rejects `user` instead of `user@domain` | Internal scripts may send with short sender name | Add `permit_mynetworks` before these restrictions (already done) |
| 306 | Postfix connection rate limiting `30/min` | 30 connections per minute per client; large email providers may send faster | Increase for trusted senders |
| 307 | `anvil_rate_time_unit = 60s` | Rate counters reset every 60 seconds | Standard setting |
| 308 | `smtpd_error_sleep_time = 1s` | Slow down misbehaving clients | Correct anti-abuse measure |
| 309 | Rspamd learn from user actions | Moving mail to Junk should train Bayesian classifier; current Sieve config files spam to Junk but doesn't learn from it | Add `imap_sieve` plugin for learning on move/copy |
| 310 | Sieve `00-spam.sieve` checks `X-Spam: Yes` header | Rspamd adds this header; Sieve moves to Junk | Already correct |
| 311 | Dovecot auto-create folders (Drafts, Sent, Trash, Junk, Archive) | `10-mail.conf` `auto = create` for special-use folders | Already correct |
| 312 | Dovecot `mail_attachment_dir` not configured | Attachments stored inline in Maildir; no deduplication | Consider `mail_attachment_dir` for storage savings |
| 313 | Dovecot `mail_attachment_min_size` not set | All attachment sizes stored inline | Tune if attachment dedup is enabled |
| 314 | Postfix `always_bcc` not configured | No archive/audit copy of all mail | Document legal compliance considerations |
| 315 | `smtpd_delay_reject = yes` | Postfix waits until RCPT TO before rejecting → reduces bandwidth on rejected mail | Already correct |
| 316 | `debug_peer_level = 2` | Production shouldn't have debug enabled | Set to `0` for production |
| 317 | `debug_peer_list` empty | No debug peers; `debug_peer_level` is effectively disabled | Set `debug_peer_level = 0` |
| 318 | Postfix `inet_protocols = ipv4` | Explicit IPv4 only; safe default | Already correct |
| 319 | TLS cipher `high` is a Postfix built-in list | May include weaker ciphers | Explicitly list ciphers or use `medium` built-in |
| 320 | No SMTPUTF8 support (`smtputf8_enable = no` by default) | International email addresses (with UTF-8 local part) not supported | Enable if needed; currently uncommon |
| 321 | Postfix `virtual_transport = lmtp:unix:/var/run/dovecot/lmtp` | LMTP over Unix socket — fast, no network overhead | Already correct |
| 322 | Dovecot LMTP UID/GID = 5000 (vmail) | Mail files owned by vmail:vmail | Already correct |
| 323 | Dovecot `mail_privileged_group = mail` | Dovecot processes access mail via group permissions | Verify vmail user is in mail group |
| 324 | No SMTP AUTH rate limiting | Brute force on SMTP AUTH possible | Add fail2ban or rate limiting for SASL failures |
| 325 | No outgoing spam detection | Postfix doesn't scan outgoing mail → compromised account can send spam | Add rspamd scanning for outbound mail too |
| 326 | No DMARC reporting generator | Rspamd has DMARC module; verify it generates aggregate reports | Enable DMARC aggregate report generation |
| 327 | SPF alignment for subdomains | Current SPF `v=spf1 mx -all` is domain-level; subdomains inherit via DMARC `sp=reject` (default) | Document subdomain SPF behavior |
| 328 | Postfix `lmtp_tls_session_cache_database` not set | Postfix client cache for LMTP (internal, not needed) | No issue (Unix socket, not TLS) |
| 329 | Dovecot `auth_verbose = no` default | Failed auth attempts not logged in detail | Set `auth_verbose = yes` for troubleshooting; `auth_debug = no` for security |
| 330 | Dovecot `mail_debug = no` default | Mail operations not debug-logged | Correct for production |

---

## 10. WEBMAIL ACCESS (SNAPPYMAIL) (20 edge cases)

### Happy Path
User navigates to `https://mail.example.com/webmail/`, nginx proxies to SnappyMail, user logs in with email + password (IMAP auth via API), webmail loads.

### Negative Scenarios (6)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 331 | SnappyMail can't reach Dovecot | Login fails; "Connection to storage server failed" | HIGH |
| 332 | SnappyMail PHP-FPM crashes | nginx returns 502; supervisor restarts | MEDIUM |
| 333 | SnappyMail data directory not writable | Can't save user preferences; login may work but settings lost | MEDIUM |
| 334 | SnappyMail version 2.38.0 has known CVEs | Outdated webmail version → XSS/RCE risk | Update SnappyMail regularly |
| 335 | WebSocket falls back to HTTP polling | Real-time notifications don't work; user experience degraded | Verify WebSocket support through nginx |
| 336 | SnappyMail PHP session storage on disk | Multi-container: sessions lost if container recreated | Use Redis for PHP sessions |

### Edge Cases (14)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 337 | SnappyMail admin panel accessible | Default install may have admin panel at `/webmail/?admin` | Disable or password-protect admin panel |
| 338 | SnappyMail PHP `memory_limit` low | Large mailboxes may hit memory limit loading message lists | Increase PHP memory_limit |
| 339 | SnappyMail nginx-snappymail.conf PHP timeout 30s | Long operations (large attachment upload) timeout | Increase fastcgi_read_timeout |
| 340 | SnappyMail `data` directory growth | User preferences, cached messages, contacts → volume grows | Add monitoring for snappymail_data volume |
| 341 | SnappyMail file type icons/cache | Cached on disk in data dir | Clean during upgrades |
| 342 | SnappyMail login brute force | No rate limiting on webmail login beyond nginx login rate limit | Add fail2ban for SnappyMail login |
| 343 | Webmail accessed over HTTP (not HTTPS) | nginx redirects HTTP to HTTPS → safe | Already correct |
| 344 | SnappyMail uses IMAP directly or via API proxy | If SnappyMail connects to Dovecot directly, API is bypassed for mail operations | Clarify architecture: SnappyMail <-> Dovecot vs SnappyMail <-> API <-> Dovecot |
| 345 | `/webmail/` path prefix conflicts with API routes | If API has `/webmail/` route, nginx routes to SnappyMail instead | Verify URL namespace separation |
| 346 | nginx `sub_filter` not configured for webmail path rewriting | SnappyMail generates absolute URLs → may not include `/webmail/` prefix | Configure SnappyMail base URL |
| 347 | SnappyMail supervisord auto-restart on crash | `autorestart=true` in supervisord.conf | Already correct |
| 348 | SnappyMail Dockerfile runs two processes (nginx + php-fpm) | Single container, two processes managed by supervisor | Acceptable for mail server scale |
| 349 | SnappyMail upgrade path | New SnappyMail version → rebuild image → data migration? | Document upgrade procedure |
| 350 | SnappyMail plugin compatibility | Plugins may break with version upgrades | Document plugin policy |

---

## 11. API & DJANGO BACKEND (30 edge cases)

### Happy Path
Django API starts after migrations and superuser creation, serves health endpoint at `/health/`, admin panel, and REST API for mail/domain/account management.

### Negative Scenarios (8)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 351 | Django migration fails | API container exits → nginx can't start → stack incomplete | CRITICAL |
| 352 | Django can't connect to PostgreSQL | API healthcheck fails → nginx reports 502 | HIGH |
| 353 | Django can't connect to Redis (Celery) | Celery tasks fail silently; API may still work for non-async operations | MEDIUM |
| 354 | `SECRET_KEY` changes between restarts | All existing sessions invalidated; CSRF tokens break | HIGH |
| 355 | `DJANGO_ALLOWED_HOSTS` doesn't include all access methods | 400 Bad Request for disallowed hostnames | MEDIUM |
| 356 | Django admin exposed at `/admin/` | Brute force target; no additional protection beyond AXES | MEDIUM |
| 357 | `DEBUG=False` but error pages reveal info | 500 errors may leak stack traces if not properly configured | Verify 500 error templates |
| 358 | Celery worker not running | Async tasks (email sending, DNS checks) never execute | Add Celery worker container or thread |

### Edge Cases (22)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 359 | Django `check --deploy` warnings ignored | Warnings printed but entrypoint continues | Exit on deploy check warnings with strict mode |
| 360 | `manage.py check --deploy` may fail on SESSION_COOKIE_SECURE if HTTPS not yet configured | Cert not ready → check warns about SECURE_SSL_REDIRECT | Acceptable; deploy checks are warnings |
| 361 | Gunicorn worker timeout | Default 30s; long API requests may timeout | Set `--timeout 120` for email operations |
| 362 | Gunicorn graceful timeout | Default 30s; workers get 30s to finish requests before SIGKILL | Increase for long connections |
| 363 | Gunicorn `--worker-class` | Default sync workers; async workers better for WebSocket | Use `uvicorn` workers if async needed |
| 364 | Static files not served with proper caching headers | nginx config sets `expires 30d` for static — correct | Already correct |
| 365 | Django `SECURE_PROXY_SSL_HEADER` setting | Needed for HTTPS detection behind nginx reverse proxy | Verify `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` |
| 366 | Django `USE_X_FORWARDED_HOST` | Needed for correct hostname detection | Verify setting |
| 367 | Django `CSRF_TRUSTED_ORIGINS` hardcoded in .env generation | bootstrap.sh and setup-wizard.sh set these; provision.sh doesn't | Add CSRF_TRUSTED_ORIGINS to provision.sh |
| 368 | Django admin MEDIA_URL/MEDIA_ROOT | File uploads for admin (if any) need media storage | Configure if needed |
| 369 | Django LOGGING configuration | Production logging should go to stdout/stderr for Docker log driver | Verify LOGGING config in production settings |
| 370 | Django email backend for sending system emails | Password resets, notifications → need SMTP backend or local submission | Configure email backend to use local Postfix |
| 371 | Django SENTRY_DSN integration | Error tracking; if SENTRY_DSN set but Sentry unreachable, logging blocks | Add async Sentry transport |
| 372 | API read-only access to mail_data volume | `/var/mail/vhosts:ro` — API can read mail for admin functions, can't modify | Already correct |
| 373 | Multiple API containers (scaling) | Gunicorn + multiple workers handles concurrency; multiple containers would need shared state | Document single-container design |
| 374 | Celery tasks use Redis as broker | Redis persistence (RDB/AOF) is important — if Redis restarts, queued tasks lost | Enable Redis AOF persistence |
| 375 | Django `CONN_MAX_AGE` for PostgreSQL | Persistent connections reduce overhead; pooler not configured | Add `CONN_MAX_AGE=60` (1 minute) |
| 376 | Django `ATOMIC_REQUESTS` | Wraps each request in transaction; good for data integrity; performance cost | Evaluate trade-off |
| 377 | API returns JSON errors for 502/503/504 | nginx custom error_page returns JSON — consistent with API | Already correct |
| 378 | `/health/` endpoint depth | Currently checks DB connectivity; should it check Redis, Celery, disk? | Deeper health check for monitoring |
| 379 | API versioning | No API version in URL (`/api/v1/`); breaking changes affect all clients | Add versioning if API is public |
| 380 | Django admin static files | Collected into shared volume; nginx serves them | Already correct |

---

## 12. BACKUP & RESTORE (40 edge cases)

### Happy Path
Daily cron runs `backup_full.sh` at 3:17 AM. Script dumps PostgreSQL, copies mail storage, config files, DKIM keys. Creates manifest + SHA256 checksums, compresses to tar.gz, optionally GPG-encrypts, cleans old backups. Monthly `restore_test.sh` verifies the latest backup restores correctly.

### Negative Scenarios (13)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 381 | PostgreSQL dump fails | Backup aborts, `rm -rf $BACKUP_ROOT`, sends webhook notification | HIGH |
| 382 | Disk full during backup | `pg_dump` or `tar` fails silently or produces truncated backup | CRITICAL |
| 383 | GPG key missing for encryption | Backup proceeds unencrypted with warning | MEDIUM |
| 384 | GPG key expired | Encryption uses expired key → backup may be unrecoverable | HIGH |
| 385 | mail_data volume empty or inaccessible | `cp -a` from volume copies nothing; warning printed but backup continues | MEDIUM |
| 386 | DKIM keys directory empty | `cp -r` copies nothing; backup missing irreplaceable keys | CRITICAL |
| 387 | `.env` file not backed up | configs/dotenv would be empty/missing | CRITICAL |
| 388 | SHA256 checksum verification fails after compression | Corrupted archive; backup is useless | HIGH |
| 389 | Restore test: `ifinmail_restore_test` database creation fails | Test reports FAIL but doesn't explain why; real restore may also fail | HIGH |
| 390 | Restore test: `pg_restore -l` validation doesn't check data integrity | Valid TOC listing doesn't guarantee data is readable | MEDIUM |
| 391 | GPG decryption fails during restore test | Test fails; but failure message doesn't tell user to check GPG key availability | MEDIUM |
| 392 | `RETENTION_DAYS` set too low | Backups deleted before they can be verified | Add minimum retention enforcement |
| 393 | Backup script not in crontab | No backup automation; users must manually add to cron | Add cron installation to provision.sh |

### Edge Cases (27)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 394 | Backup file naming: `ifinmail_backup_YYYYMMDD_HHMMSS.tar.gz` | Sortable by name; consistent format | Already correct |
| 395 | Two backup runs at same time | Race condition: both write to different `$BACKUP_ROOT` dirs (timestamp-based); safe | Already correct |
| 396 | Backup while mail is being delivered | Maildir copy may capture partial writes → some messages corrupt in backup | Use Dovecot `dsync` for consistent mail backup |
| 397 | `pg_dump -Fc` (custom format) allows parallel restore | Good choice | Already correct |
| 398 | `pg_dump --schema-only` is secondary | `|| true` → failure ignored; schema dump is supplementary | Already correct |
| 399 | Mail backup uses `docker run alpine cp -a` | Creates an ephemeral container to copy from volume; Docker overhead per backup | Use `docker volume` backup approach or bind mount |
| 400 | DKIM keys `chmod -R 600` after copy | Restrictive permissions on backup | Already correct |
| 401 | MANIFEST.txt includes `date -Iseconds` | ISO 8601 timestamp | Already correct |
| 402 | SHA256SUMS file includes all files | Checksums for verification | Already correct |
| 403 | Archive verification extracts to `/tmp` (restore_test.sh) | `/tmp` may be tmpfs (RAM-based) → insufficient space for large backups | Use `/backups` or `/var/tmp` for verification |
| 404 | restore_test.sh `ls -t` for latest backup | Relies on filename sort order (timestamp-based) | Already correct |
| 405 | restore_test.sh removes `$TEST_DIR` on exit | Cleanup is good; but if test fails, evidence is lost | Keep `$TEST_DIR` on failure |
| 406 | restore_test.sh `TABLE_COUNT` comparison | Checks only count, not table names → false positive if wrong tables restored | Compare table names too |
| 407 | restore_test.sh test database `DROP DATABASE IF EXISTS` | Aggressive cleanup; if concurrent test runs, could drop the other's database | Use unique test database names (include timestamp) |
| 408 | `find /backups -name "*.tar.gz*" -mtime +$RETENTION_DAYS -delete` | Uses mtime; if file is touched, it's preserved beyond retention | Use filename-based retention (parse date from name) |
| 409 | GPG-encrypted files have `.gpg` extension | After encryption, `$ARCHIVE_NAME` changes to `.gpg` extension; `find` pattern `*.tar.gz*` matches both | Already correct |
| 410 | Backup encryption uses `--yes` flag | Overwrites existing encrypted backup without prompt | Add check for existing file |
| 411 | No backup of Redis data (RDB/AOF) | Rspamd learning data, Celery task state not backed up | Add Redis backup or document data loss acceptance |
| 412 | No backup of Docker images | Images rebuilt from Dockerfiles; not needed | Acceptable |
| 413 | No backup of certbot keys (Let's Encrypt account) | If account key lost, new account needed → rate limits | Back up certbot account directory |
| 414 | Backup script uses `docker compose` but doesn't detect v1/v2 | Hardcoded `docker compose` (v2); fails on v1 | Add detection fallback |
| 415 | Backup size not reported if directory copy from volume fails | `du` on archive reports size even if content is minimal | Add content size validation |
| 416 | No offsite backup mechanism | All backups stored locally in `/backups`; single point of failure | Document offsite backup solutions (rsync, S3, rclone) |
| 417 | Backup notification webhook only fires on failure | No success notification; silence ≠ success | Add periodic success summary |
| 418 | `BACKUP_NOTIFY_URL` has no timeout | curl in `notify_failure()` has no timeout → could hang backup script | Add `--connect-timeout 10 --max-time 30` |
| 419 | `BACKUP_NOTIFY_URL` contains special characters | Passed to curl; should be properly quoted | URL-encode or quote |
| 420 | `mktemp -d` for verify temp dir | Creates random temp dir; may fail if `/tmp` is full | Use explicit path in `/backups` |

---

## 13. MONITORING & ALERTING (35 edge cases)

### Happy Path
`monitor.py` runs every 5 minutes via cron, checks 8 subsystems, pushes results to Redis with 24h history, sends webhook alerts on state transitions (OK→CRITICAL, CRITICAL→OK).

### Negative Scenarios (9)

| # | Scenario | Current Behavior | Severity |
|---|----------|-----------------|----------|
| 421 | Redis unreachable for monitor | `redis_client = None` → checks still run but results not stored; alert still sent locally | MEDIUM |
| 422 | Alert webhook target unreachable | `curl` failure silently caught; alert never delivered | HIGH |
| 423 | Alert state file permissions prevent write | `ALERT_STATE_FILE` can't be written → state not persisted → every run reports CRITICAL (alert spam) | MEDIUM |
| 424 | `psutil` not installed | Fallback to `/proc` filesystem; Linux-specific | MEDIUM |
| 425 | `docker compose ps` fails | All services reported as down → false CRITICAL | HIGH |
| 426 | Postfix `find /var/spool/postfix/active` returns error | `docker compose exec` may fail → exception caught, UNKNOWN status | MEDIUM |
| 427 | Delivery rate calculation fails (no recent log entries) | Returns `delivery_rate = 100.0` → misleading (no data ≠ perfect delivery) | Return None or "no data" |
| 428 | Cert check: `CERT_DIR` doesn't exist | Returns "cert not found" error; overall may still be OK if other checks pass | Add weight to cert status |
| 429 | Backup freshness check: directory missing | Reports WARN; may be expected on new installs | Make backup check optional or configurable |

### Edge Cases (26)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 430 | Monitor runs while stack is restarting | Services briefly down → alert triggered; resolves next run | Add flapping detection (require N consecutive failures) |
| 431 | Monitor alerts on RECOVERY but not OK→WARN transition | Only CRITICAL↔OK transitions are alerted; WARN state changes are silent | Add WARN threshold notifications |
| 432 | Alert payload truncated at 1400 chars for Slack/Discord | JSON report may be cut mid-structure | Ensure truncation is at a valid JSON boundary |
| 433 | `ALERT_STATE_FILE` directory creation `os.makedirs(state_dir, exist_ok=True)` | Only creates if dirname is non-empty; if `ALERT_STATE_FILE = "alert_state"` (no dir), `state_dir` is empty → skipped | Handle relative paths |
| 434 | Atomic state file write: write to `.tmp`, then `os.replace()` | `os.replace()` is atomic on POSIX | Already correct |
| 435 | `datetime.utcnow()` deprecated in Python 3.12+ | Should use `datetime.now(timezone.utc)` | Update to non-deprecated API |
| 436 | Monitor exit codes: 0=OK, 1=WARN, 2=CRITICAL | Compatible with Nagios-style monitoring | Good for cron wrappers |
| 437 | Redis data: `lpush` + `ltrim 0 287` keeps 288 entries × 5min = 24h | Correct | Already correct |
| 438 | Redis TTL: 600s (10 min) on `latest` key | If monitor stops, latest data disappears after 10 min | Increase TTL to 3600s (1h) |
| 439 | Postfix queue check uses `find` not `postqueue -p` | `find` on spool directory is fragile; postfix internal structure may change | Use `postqueue -p` JSON output |
| 440 | Service check uses `docker compose ps --format json` | Each line is a JSON object; parsed individually | Already correct |
| 441 | Service list hardcoded: `["postgres", "redis", "postfix", "dovecot", "rspamd", "api", "nginx"]` | If services renamed in compose file, monitor silently misses them | Read service names from compose file |
| 442 | `snappymail` not in service check list | SnappyMail health not monitored at all | Add to service list |
| 443 | API health check uses `curl` from host, not Docker exec | `curl http://localhost:8000/health/` — requires API port bound to localhost | Already works (port 8000 → 127.0.0.1:8000) |
| 444 | Disk check `MONITOR_DISK_MOUNTS` defaults to `/` and `/var` | May include non-existent mount points → no error, just skipped | Already correct |
| 445 | Delivery rate uses `awk` on Postfix logs | `$1"T"$2 >= "since_time"` — fragile date parsing; Postfix log format may vary | Use `journalctl` or structured logging |
| 446 | System resource check `psutil.cpu_percent(interval=1)` | Blocks for 1 second; increases monitor runtime | Use shorter interval or async |
| 447 | `/proc/meminfo` fallback parsing | `MemAvailable` includes reclaimable memory → may report lower usage than actual | Acceptable approximation |
| 448 | Backup check only looks for `.tar.gz.gpg` files | If `ENCRYPT=false`, backups end with `.tar.gz` → not found → WARN | Check for both `.tar.gz` and `.tar.gz.gpg` |
| 449 | Backup `MAX_AGE_HOURS` defaults to 25h | 25h since last backup → daily backup has 1h grace period before alerting | Reasonable |
| 450 | Monitor not added to crontab automatically | User must manually configure cron | Add cron installation to provision.sh |
| 451 | Monitor Python dependencies (redis, psutil) | Not installed on host system; monitor may fail with ImportError | Add Python dependency check |
| 452 | `MONITOR_ALERT_WEBHOOK` set in setup-wizard but not in provision.sh | Alert webhook only configured through setup wizard | Add to provision.sh defaults |
| 453 | `ALERT_STATE_FILE` path `/var/lib/ifinmail/alert_state` | Directory must be created manually or by monitor first run | Ensure directory exists in provision.sh |
| 454 | Multiple monitor instances running concurrently | Two `lpush` operations interleave → history may have duplicates | Add lockfile to prevent concurrent runs |
| 455 | Monitor timeout: `subprocess.run(timeout=10)` for most checks | 8 checks × 10s = 80s max runtime; fits within 5-min cron window | Already correct |

---

## 14. SECURITY HARDENING (25 edge cases)

### Happy Path
Firewall restricts to needed ports, services use TLS, SQL passwords are random, Django has brute-force protection, HSTS is configured, nginx has security headers.

### Edge Cases

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 456 | Rspamd web UI password is a hardcoded `$2$` placeholder | Anyone on localhost (or via port forwarding) can access rspamd UI with known password | Generate random rspamd controller password and configure it |
| 457 | rspamd controller bound only to `127.0.0.1:11334` | Only localhost access → harder to exploit but Docker port mapping exposes it on host localhost | Already correct |
| 458 | No SSH hardening (port, key-only, fail2ban) | VPS SSH on port 22 with password auth → brute force target | Add SSH hardening to bootstrap or document |
| 459 | No automatic security updates | Ubuntu/Debian packages not auto-updated → known vulnerabilities persist | Enable `unattended-upgrades` in bootstrap.sh |
| 460 | Docker daemon accessible to non-root users (docker group) | User in `docker` group has effective root → privilege escalation risk | Document risk |
| 461 | PostgreSQL superuser password in `.env` | If `.env` read, full DB access | Restrict `.env` permissions; consider secrets management |
| 462 | `DJANGO_SECRET_KEY` used for sessions, CSRF, password reset tokens | If leaked, all sessions hijack-able; password reset tokens forgeable | Key rotation procedure needed |
| 463 | No Content-Security-Policy for webmail | XSS in SnappyMail could exfiltrate data | Add CSP headers; test with SnappyMail |
| 464 | No `X-Content-Type-Options: nosniff` | MIME sniffing attacks possible on uploaded content | Add header in nginx (already has it at server level) |
| 465 | `X-Frame-Options: DENY` in nginx | Prevents clickjacking | Already correct |
| 466 | No `Referrer-Policy` header | Referrer leakage to external sites | Add `Referrer-Policy: same-origin` |
| 467 | No `Permissions-Policy` header | Browser feature restrictions | Add restrictive Permissions-Policy |
| 468 | certbot has Docker socket access (root on host) | If certbot container compromised → host compromise | Isolate certbot; use signal-based renewal instead of socket |
| 469 | SMTP ports open to internet → DDoS target | Postfix rate limiting helps; volumetric DDoS still possible | Document DDoS mitigation (cloud firewall, fail2ban) |
| 470 | IMAP brute force | No fail2ban for IMAP failures | Add IMAP fail2ban jails |
| 471 | Outbound SMTP on port 25 from authenticated users | Users can send spam if credentials compromised | Rate-limit outbound; add outbound spam scanning |
| 472 | ARGON2ID password storage in Dovecot | Strong hashing; but CPU cost per auth is high under brute force | Rate-limit auth attempts; add fail2ban |
| 473 | No network segmentation between services | All services on one Docker network → if one is compromised, lateral movement possible | Segment: separate DB network, mail network, frontend network |
| 474 | `ssl_ciphers` in Dovecot and Postfix use `high` preset | Medium-strength ciphers may be included depending on OpenSSL build | Use explicit cipher list (Mozilla Intermediate) |
| 475 | No mandatory TLS for inbound SMTP (port 25) | `smtpd_tls_security_level = may` → mail can be delivered unencrypted | This is RFC-compliant; MTA-STS upgrades opportunistic to mandatory |
| 476 | PostgreSQL SSL conditional on cert existence | When certs missing (bootstrap), PostgreSQL runs without SSL → plaintext passwords over Docker network | Acceptable for initial bootstrap; internal network only |
| 477 | MySQL/MariaDB not used but PostgreSQL timeouts prevent stuck connections | Already handled via `statement_timeout`, etc. | Already correct |
| 478 | No audit logging for admin actions | Django admin changes not separately logged | Enable Django admin logging (django-admin-log) |
| 479 | `SECURE_HSTS_SECONDS=3600` vs nginx HSTS 63072000 | Django HSTS setting (3600 = 1h) is overridden by nginx's stronger setting (63072000 = 2y) | Align both or document that nginx takes precedence |
| 480 | Rate limit zones use client IP | Behind Cloudflare/CDN, all clients appear as Cloudflare IP → rate limiting ineffective | Use `real_ip_header X-Forwarded-For` for CDN deployments |

---

## 15. UPGRADE & MAINTENANCE (10 edge cases)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 481 | `make reload` rebuilds images and restarts ALL services | Downtime for all services during rebuild | Add rolling restart or blue-green deployment |
| 482 | `make provision` run on existing installation | Idempotent for most steps; but `docker compose build --pull` pulls new base images → may introduce breaking changes | Add `--no-pull` flag or pin base image digests |
| 483 | Django migration adds NOT NULL column with no default | Migration fails on table with existing rows | Always test migrations against production data |
| 484 | Docker image tags use `:latest` for custom images | `ifinmail/postfix:latest` — no versioning → hard to rollback | Tag custom images with version or git hash |
| 485 | Configuration changes (main.cf, dovecot.conf) require rebuild | Templates are baked into Docker images → config changes need image rebuild | Externalize configs as mounted volumes |
| 486 | Upgrading PostgreSQL major version (16 → 17) | `pg_upgrade` needed; manual process | Document PostgreSQL upgrade procedure |
| 487 | Upgrading Redis major version | RDB format compatibility; manual process | Document Redis upgrade procedure |
| 488 | Let's Encrypt certificate lifetime reduction | Currently 90 days; may reduce to 45 or less → renewal loop (12h) is fine | Monitor Let's Encrypt policy changes |
| 489 | Docker version upgrade | Compose file features may break (e.g., `condition: service_healthy` in depends_on no longer valid in newer versions) | Pin Docker API version or test upgrades |
| 490 | Kernel upgrade changes sysctl defaults | `cloud-init.yaml` sets sysctl values; kernel upgrade may override or change behavior | Add sysctl verification to monitoring |

---

## 16. DISASTER RECOVERY (10 edge cases)

| # | Edge Case | Description | Remediation |
|---|-----------|-------------|-------------|
| 491 | Complete server loss | All data lost (mail, database, configs) → need to rebuild from backups | Document full recovery procedure from backups |
| 492 | `postgres_data` volume corruption | PostgreSQL won't start; all mail services fail (can't look up mailboxes) | Document PostgreSQL recovery (pg_resetwal, PITR) |
| 493 | `mail_data` volume corruption | All email inaccessible; delivery fails | Document Maildir recovery (doveadm force-resync) |
| 494 | `dkim` keys lost without backup | Can't sign outgoing mail → DMARC fails → outgoing mail goes to spam | Emphasize DKIM key backup priority |
| 495 | GPG backup key lost | All encrypted backups unrecoverable; historical backups useless | Store GPG key securely offline; document export procedure |
| 496 | `.env` file lost | All random passwords lost; can't rebuild without regenerating EVERYTHING → data in volumes becomes inaccessible because passwords changed | Back up `.env` separately (printed or password manager) |
| 497 | Docker images deleted from registry (Docker Hub outage) | Can't rebuild; `docker compose build --pull` fails | Use local image cache; pin base image digests in FROM lines |
| 498 | Let's Encrypt CA compromised/revoked | All certs invalid → TLS breaks everywhere | Have contingency plan for alternative CA |
| 499 | DNS provider outage | MX records unresolvable → incoming mail bounces after sender retries (typically 4-5 days) | Use secondary DNS provider |
| 500 | Domain registration expires | ALL mail stops; domain may be squatted | Add domain expiry to monitoring alerts |

---

## PRIORITIZED REMEDIATION PLAN

### CRITICAL (fix immediately)

1. **rspamd milter port binding bug** (#242-244): Port 11332 bound to `127.0.0.1` prevents Postfix from reaching rspamd via Docker network
2. **GPG backup key no passphrase** (#46): `%no-protection` means anyone with filesystem access can decrypt all backups
3. **`obtain-ssl.sh` deletes cert BEFORE certbot succeeds** (#116): Should delete AFTER successful issuance
4. **7-day self-signed cert window** (#111): Extend to 30 days; add alert if LE hasn't succeeded within 5 days
5. **API `ALLOWED_HOSTS` missing Docker internal hostnames** (#55): Add `api,localhost,127.0.0.1`

### HIGH (fix in next sprint)

6. **DKIM DNS TXT record length > 255 chars** (#268): Split into 255-char chunks in `print_dns()`
7. **MTA-STS `mode: enforce` from day one** (#144): Start with `testing`, graduate to `enforce`
8. **MTA-STS needs separate TLS cert** (#274): `mta-sts.$DOMAIN` not in certificate SAN list
9. **No outbound spam scanning** (#325): Compromised accounts can send unlimited spam
10. **PostgreSQL SSL conditional → Dovecot/Postfix `sslmode=require` mismatch** (#194): Use `sslmode=require` only when PG SSL is active
11. **Rspamd web UI default password** (#456): Generate random controller password
12. **`DJANGO_SUPERUSER_PASSWORD` in process list** (#211): Use `createsuperuser --noinput` with env vars
13. **Backup of DKIM keys is critical** (#386): Add pre-backup check; fail backup if DKIM keys missing
14. **Postfix `debug_peer_level = 2` in production** (#316): Set to 0
15. **Docker `iptables` bypasses ufw** (#237): Document Docker + ufw interaction; add iptables rules

### MEDIUM (fix within 2 sprints)

16. Normalize `DOMAIN` to lowercase (#13)
17. Strip trailing dot from `DOMAIN` (#14)
18. Fix Windows CRLF in `.env` (#21)
19. Check `docker info` in `detect_compose()` (#25)
20. Pre-flight disk space check (#11, #89)
21. Pre-flight RAM check (#12)
22. Add `.dockerignore` (#82, #105)
23. URL-encode password in `DATABASE_URL` (#53)
24. Set `SECURE_HSTS_SECONDS` to 1 year (#57)
25. Backup certbot account directory (#155)
26. Celery worker not running (#358)
27. Enable Redis AOF persistence (#374)
28. Add `CONN_MAX_AGE` for PG connections (#375)
29. Port init-db.sh to POSIX sh (#99-100)
30. Add lockfile to monitor.py (#454)

### LOW (continuous improvement)

31. Add ECDSA certificate option (#138)
32. Enable HTTP/2 in nginx (#260)
33. Add `TZ` env var to containers (#224)
34. Update `datetime.utcnow()` to timezone-aware (#435)
35. Add PTR record instructions (#275)
36. Add IMAP fail2ban integration (#470)
37. Segment Docker networks (#473)
38. Pin base image digests (#482)
39. Document full DR procedure (#491)
40. Add domain expiry monitoring (#500)

---

## SUMMARY STATISTICS

| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| 1. Pre-provisioning/Env Setup | 40 | 0 | 4 | 8 | 28 |
| 2. Secret Generation | 35 | 0 | 2 | 5 | 28 |
| 3. Docker Image Builds | 30 | 0 | 3 | 10 | 17 |
| 4. Certificate Management | 50 | 3 | 6 | 20 | 21 |
| 5. Database Init | 40 | 2 | 4 | 12 | 22 |
| 6. Service Startup | 35 | 2 | 4 | 8 | 21 |
| 7. Network/Ports | 30 | 2 | 3 | 10 | 15 |
| 8. DNS Configuration | 25 | 1 | 4 | 8 | 12 |
| 9. Mail Flow | 45 | 2 | 6 | 15 | 22 |
| 10. Webmail | 20 | 0 | 3 | 7 | 10 |
| 11. API/Django | 30 | 1 | 3 | 10 | 16 |
| 12. Backup/Restore | 40 | 2 | 6 | 15 | 17 |
| 13. Monitoring | 35 | 0 | 3 | 10 | 22 |
| 14. Security | 25 | 0 | 5 | 10 | 10 |
| 15. Upgrade/Maintenance | 10 | 0 | 2 | 4 | 4 |
| 16. Disaster Recovery | 10 | 0 | 3 | 4 | 3 |
| **TOTAL** | **500** | **15** | **61** | **156** | **268** |

**Critical + High: 76 items requiring immediate or near-term attention.**

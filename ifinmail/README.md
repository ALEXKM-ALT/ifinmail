# ifinmail

Self-hosted email platform — run your own mail server on a single VPS. Handles SMTP, IMAP, spam filtering, TLS, DKIM signing, and backups. Built on Django, Postfix, Dovecot, Rspamd, PostgreSQL, and Redis, all containerized with Docker Compose.

## Quickstart

**Prerequisites**: a domain name, a VPS running Ubuntu 22.04+ or Debian 12+ with a public IPv4 address, and port 25 unblocked by your provider.

### Option 1: One-Click Deploy

[![Deploy to DigitalOcean](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/droplets/new?size=s-2vcpu-4gb&region=nyc1&image=ubuntu-24-04-x64&user_data=<cloud-init-url>)

Copy the [cloud-init.yaml](provisioning/cloud-init.yaml) content into your cloud provider's "User data" field when creating a server. Set the `DOMAIN` and `ADMIN_EMAIL` environment variables. Works with DigitalOcean, Hetzner Cloud, AWS EC2, Linode, and any provider that supports cloud-init.

### Option 2: Terminal (one command)

```bash
curl -sSL https://raw.githubusercontent.com/ifinmail/ifinmail/main/provisioning/scripts/bootstrap.sh | sudo bash
```

This installs Docker, clones the repo, runs an interactive setup wizard, and provisions the full stack. Answer the prompts with your domain and admin email — everything else is generated automatically.

For fully automated deployment, use non-interactive mode:

```bash
export DOMAIN=example.com ADMIN_EMAIL=admin@example.com
curl -sSL https://raw.githubusercontent.com/ifinmail/ifinmail/main/provisioning/scripts/bootstrap.sh | sudo bash -s -- --non-interactive
```

## DNS Records

After provisioning, create these DNS records for your domain. The provisioning script prints the exact values — especially the DKIM public key, which is unique to your installation.

| Type | Name | Value |
|------|------|-------|
| A | `yourdomain.com` | Your VPS IPv4 address |
| A | `mail.yourdomain.com` | Your VPS IPv4 address |
| MX | `yourdomain.com` | `10 mail.yourdomain.com.` |
| TXT | `yourdomain.com` | `v=spf1 mx -all` |
| TXT | `_dmarc.yourdomain.com` | `v=DMARC1; p=quarantine; rua=mailto:postmaster@yourdomain.com` |
| TXT | `default._domainkey.yourdomain.com` | `v=DKIM1; k=rsa; p=<your-public-key>` |

### DNS Provider Guides

**Cloudflare**: create A records with the orange cloud **off** (DNS-only, not proxied). MX and TXT records go under DNS → Records → Add Record.

**Namecheap**: go to Domain List → Manage → Advanced DNS. Use `@` for the root domain and `mail` for the mail subdomain.

**Porkbun**: go to Domain Management → DNS → Edit. Use the empty/blank host field for root records.

## Logging In

After provisioning, the admin panel is at `https://mail.yourdomain.com/django-admin/`. Log in with the admin username and password printed during setup (also stored in `provisioning/.env`).

### Creating Your First Mailbox

1. Go to Domains → Add domain (your domain should already be listed)
2. Go to Mailboxes → Add mailbox (choose your domain, enter the local part like `hello`)
3. Go to Users → Add mail user (email must match the mailbox)
4. Configure your email client using the settings from the admin dashboard's "Email Setup" page

## Managing the Stack

```bash
make ps          # Show container status
make logs        # Tail all service logs
make health      # Run health checks
make up          # Start the stack
make down        # Stop the stack
make reload      # Rebuild images and redeploy
make backup      # Run a full backup (schedule this daily via cron)
make firewall    # Configure ufw firewall rules
```

## Troubleshooting

### "Port 25 is blocked"
Many VPS providers (AWS, GCP, DigitalOcean) block outbound port 25 by default to prevent spam. You must request them to unblock it. Without port 25, your server cannot receive mail from other servers.

### "Let's Encrypt certificate issuance failed"
The bootstrap script creates a self-signed certificate so the stack starts immediately. For a trusted certificate:
1. Verify DNS A records for your domain and mail subdomain point to your VPS
2. Verify port 80 is open
3. Run `make provision` again after DNS propagates

### "Mail goes to spam"
New IP addresses have no reputation. To improve deliverability:
- Verify all DNS records (SPF, DKIM, DMARC) are correct using `make health`
- Set up a reverse DNS (PTR) record for your VPS IP pointing to `mail.yourdomain.com` (ask your VPS provider)
- Warm up your IP by sending small volumes of mail gradually over several weeks

### "Can't connect with my email client"
Check the admin dashboard's Email Setup page for the correct server settings:
- IMAP server: `mail.yourdomain.com`, port 993, SSL/TLS
- SMTP server: `mail.yourdomain.com`, port 587, STARTTLS
- Username: your full email address

## Architecture

```
nginx (443) → api (Django, gunicorn, port 8000)
              ├── postgres (5432) — domains, users, mailboxes, aliases
              ├── redis (6379) — cache, sessions, celery broker
              ├── postfix (25, 465, 587) — SMTP, virtual lookups via pgsql
              │   └── rspamd (11332) — milter-based spam filtering
              └── dovecot (143, 993) — IMAP, LMTP delivery from postfix
```

## License

MIT

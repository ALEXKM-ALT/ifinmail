# Week 12: Capstone Project — Mini-ifinmail

**Month 3: Integration & Capstone | Days 67–72**

The capstone project integrates everything from the previous 11 weeks into a working prototype. Attaches will configure the full mail stack, build the API, create the webmail UI, set up email authentication, deploy behind TLS, and present a live demo. This is not a toy project — it should send real mail, receive real mail, and demonstrate the core ifinmail value proposition.

---

## Learning Goals for the Week

By Saturday (demo day), you will have:

- A working Postfix + Dovecot + Rspamd stack on your development server
- A Python FastAPI backend exposing Auth, Mail, and Admin APIs
- A framework-free webmail UI with `.ifinmail-*` CSS prefixing
- SPF, DKIM, and DMARC configured for your test domain
- TLS on all services
- A live demo: send mail, receive mail, read inbox in browser, view admin dashboard

---

## Capstone Requirements

### Minimum Viable Product (MVP)

Your mini-ifinmail MUST:

1. **Send and receive email** via SMTP (Postfix) for at least one domain
2. **Read mail via IMAP** (Dovecot) or the ifinmail API
3. **Display inbox in a browser** using the framework-free webmail UI
4. **Authenticate users** via the Auth API (JWT tokens)
5. **Sign outbound mail with DKIM** (Rspamd)
6. **Verify inbound SPF and DMARC** (Rspamd)
7. **Serve everything over TLS** (Certbot or self-signed for dev)
8. **Show DNS health** on the admin dashboard

### Stretch Goals (for extra recognition)

- Implement the Device Bootstrap API and manifest
- Add full-text search via PostgreSQL FTS
- Build a Rust mail parsing library callable from Python
- Containerize everything with Docker Compose
- Implement rate limiting based on trust levels

---

## Daily Breakdown

### Day 1 (Monday): Planning & Mail Stack Setup

**Morning: Architecture Review & Task Assignment**

Review the full architecture and divide into work streams:

| Work Stream | Components | Owner |
|---|---|---|
| Mail Infrastructure | Postfix, Dovecot, Rspamd | Team member A |
| API Layer | FastAPI (Auth, Mail, Admin routes) | Team member B |
| Database | PostgreSQL schema, seed data, migrations | Team member B (shared) |
| Frontend | Webmail UI, Admin dashboard, CSS system | Team member C |
| Security | TLS certs, DNS records (SPF/DKIM/DMARC) | Team member A (shared) |
| Integration | Docker Compose, health checks, deployment | All |

**Afternoon: Mail Stack Setup**

```bash
# Team member A: Get the mail stack running
# Use guides from Weeks 5-7 as reference

# 1. Install and configure Postfix
sudo apt install -y postfix postfix-pgsql
sudo postconf -e "myhostname = mail.capstone.local"
sudo postconf -e "virtual_mailbox_domains = hash:/etc/postfix/virtual/virtual_domains"
# ... (see Week 5 for full configuration)

# 2. Install and configure Dovecot
sudo apt install -y dovecot-core dovecot-imapd dovecot-lmtpd
# ... (see Week 6 for full configuration)

# 3. Install and configure Rspamd
sudo apt install -y rspamd
# ... (see Week 7 for full configuration)

# 4. Verify the stack
echo "Test message" | mail -s "Capstone Test" trainee@capstone.local
sudo tail -20 /var/log/mail.log
```

**Deliverable by end of day**: Postfix + Dovecot + Rspamd running. Test message delivered to Maildir.

---

### Day 2 (Tuesday): Database & API Layer

**Morning: Database Setup**

```sql
-- Create the capstone schema (using Week 4 patterns)
-- Core tables: organizations, domains, users, mailboxes, messages_meta, devices, sessions

CREATE SCHEMA IF NOT EXISTS ifinmail;

CREATE TABLE ifinmail.organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ... (full schema from Week 4)
```

**Afternoon: API Implementation**

```python
# Implement the three API groups (using Week 8 patterns)
# Minimum endpoints required:

# Auth API:
#   POST /v1/auth/register
#   POST /v1/auth/login
#   POST /v1/auth/refresh

# Mail API:
#   GET  /v1/mail/mailboxes
#   GET  /v1/mail/messages
#   GET  /v1/mail/messages/{id}
#   POST /v1/mail/messages

# Admin API:
#   GET  /v1/admin/deliverability
#   GET  /v1/admin/domains/{id}/dns-health
```

```bash
# Test the API
curl -s http://localhost:8000/v1/health | python3 -m json.tool
curl -s -X POST http://localhost:8000/v1/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"test@capstone.local","password":"demo123","name":"Test User"}' | python3 -m json.tool
```

**Deliverable by end of day**: Database schema populated, API responding to requests, auth flow working.

---

### Day 3 (Wednesday): Frontend — Webmail & Admin

**Morning: Webmail UI**

Build the three-panel webmail interface (using Week 10 patterns):
- Sidebar with mailbox list
- Message list with unread indicators
- Message reading pane
- Compose panel (can be a modal or separate page)
- All CSS prefixed with `.ifinmail-*`

**Afternoon: Admin Dashboard**

Build the admin dashboard:
- Platform overview with stats cards
- DNS health indicators per domain
- Deliverability metrics
- Domain and user management forms

```html
<!-- The web client should be served from the same FastAPI app -->
<!-- Add Jinja2 template rendering to the API server -->
```

```bash
# Verify the web UI
curl -s http://localhost:8000/ | head -20  # Should return HTML
curl -s http://localhost:8000/admin | head -20
```

**Deliverable by end of day**: Webmail UI shows messages from the API. Admin dashboard shows DNS health.

---

### Day 4 (Thursday): Email Authentication & Security

**Morning: DNS & Email Authentication**

```bash
# 1. Generate DKIM keys
openssl genrsa -out /etc/dkim/default.capstone.local.key 2048
openssl rsa -in /etc/dkim/default.capstone.local.key -pubout -out /etc/dkim/default.capstone.local.pub

# 2. Configure Rspamd DKIM signing
# Add domain → key mapping in /etc/rspamd/local.d/dkim_signing.conf

# 3. Set up SPF record (for your test domain)
# v=spf1 mx -all

# 4. Set up DMARC record
# v=DMARC1; p=quarantine; rua=mailto:dmarc@capstone.local

# 5. Configure MTA-STS (optional)
# Served via HTTPS at https://mta-sts.capstone.local/.well-known/mta-sts.txt

# 6. Run the DNS health checker from Week 7
python3 dns_health_checker.py capstone.local
```

**Afternoon: TLS & Security Hardening**

```bash
# 1. Obtain TLS certificate (or use self-signed for dev)
sudo certbot certonly --standalone -d mail.capstone.local --dry-run
# Or generate self-signed:
# openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 30 -nodes

# 2. Configure TLS on all services
sudo postconf -e "smtpd_tls_cert_file = /etc/postfix/certs/cert.pem"
sudo postconf -e "smtpd_tls_key_file = /etc/postfix/certs/key.pem"

# 3. Set up firewall
sudo ufw allow 22,25,465,587,143,993,80,443/tcp
sudo ufw enable

# 4. Run security verification
python3 monitor.py  # From Week 11 — should show all OK
```

**Deliverable by end of day**: DKIM signing active, SPF/DMARC records published, TLS enabled on all services.

---

### Day 5 (Friday): Integration, Testing & Polish

**Morning: End-to-End Testing**

Write and run an end-to-end test script:

```python
#!/usr/bin/env python3
"""capstone_e2e_test.py — verifies the full ifinmail stack."""
import requests
import smtplib
import imaplib
import ssl
import json

BASE = "https://mail.capstone.local"
EMAIL = "test@capstone.local"
PASSWORD = "demo123"

def test_health():
    r = requests.get(f"{BASE}/v1/health", verify=False)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    print("[PASS] Health check")

def test_auth():
    # Register and login
    r = requests.post(f"{BASE}/v1/auth/login", json={
        "email": EMAIL, "password": PASSWORD
    }, verify=False)
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    print("[PASS] Authentication")
    return data["access_token"]

def test_mail_api(token):
    # List mailboxes
    r = requests.get(f"{BASE}/v1/mail/mailboxes", 
                     headers={"Authorization": f"Bearer {token}"}, verify=False)
    assert r.status_code == 200
    assert "mailboxes" in r.json()
    print("[PASS] Mail API — list mailboxes")

def test_smtp():
    # Send a test email via SMTP submission
    context = ssl.create_default_context()
    with smtplib.SMTP("mail.capstone.local", 587) as server:
        server.starttls(context=context)
        # Login and send would go here in production
        print("[PASS] SMTP — connection to submission port")

def test_imap():
    # Connect to IMAP
    context = ssl.create_default_context()
    with imaplib.IMAP4_SSL("mail.capstone.local", 993, ssl_context=context) as conn:
        print("[PASS] IMAP — connection established")

def test_web_ui():
    r = requests.get(f"{BASE}/", verify=False)
    assert r.status_code == 200
    assert "ifinmail-shell" in r.text
    print("[PASS] Web UI — HTML served with correct CSS class")

def test_admin():
    r = requests.get(f"{BASE}/admin", verify=False)
    assert r.status_code == 200
    print("[PASS] Admin Dashboard — accessible")

if __name__ == "__main__":
    print("=== ifinmail Capstone E2E Test ===\n")
    test_health()
    test_smtp()
    test_imap()
    test_web_ui()
    test_admin()
    token = test_auth()
    test_mail_api(token)
    print("\n=== All tests passed! ===")
```

**Afternoon: Polish & Documentation**

- Fix any rough edges in the UI
- Ensure error messages are clear and useful
- Add a README to the capstone project explaining:
  - Architecture overview
  - How to start/stop services
  - API documentation link (OpenAPI)
  - Test accounts and credentials
  - Known limitations

**Deliverable by end of day**: All end-to-end tests passing. Project documented.

---

### Day 6 (Saturday): Demo Day

**Morning: Rehearsal**

Run through the full demo flow:

1. **Show the mail stack**: `systemctl status postfix dovecot rspamd` — all green
2. **Send an email**: Use the webmail compose panel
3. **Show delivery**: Check Postfix logs, show the message in Maildir
4. **Receive an email**: Send from external address (Gmail, etc.) to your test domain
5. **Read in webmail**: Log into webmail UI, show the message in inbox
6. **Show admin dashboard**: DNS health indicators, deliverability metrics
7. **Show API documentation**: Open `/v1/docs` — the auto-generated Swagger UI
8. **Show email authentication**: `dig TXT <domain>` for SPF/DKIM/DMARC records

**Afternoon: Presentation**

Prepare a 10-minute presentation covering:

1. **What we built** — the mini-ifinmail prototype
2. **Architecture** — the five-layer model from the proposal
3. **Key technical decisions** — Postfix over custom SMTP, Rust for core, vanilla frontend
4. **Challenges encountered** — what was hardest, what you would do differently
5. **Live demo** — the flow above
6. **Next steps** — what would be needed for production readiness

**Deliverable**: Working demo presented to instructors and peers.

---

## Capstone Rubric

| Criteria | Weight | Expectation |
|---|---|---|
| Mail Delivery | 25% | Send and receive email via SMTP. Messages land in Maildir. |
| API Completeness | 20% | Auth (register/login), Mail (list/read/send), Admin (DNS health) endpoints all work. |
| Frontend | 20% | Webmail UI with three-panel layout, `.ifinmail-*` CSS prefixing, admin dashboard. |
| Email Authentication | 15% | SPF, DKIM (signing), and DMARC configured. DNS health checker reports correctly. |
| Security | 10% | TLS on all services, Argon2id password hashing, JWT auth, firewall configured. |
| Integration & Polish | 10% | End-to-end tests pass, error handling is consistent, documentation is clear. |

---

## Capstone Submission Checklist

Before presenting, confirm:

- [ ] Postfix is running and accepting mail on ports 25, 587
- [ ] Dovecot is serving IMAP on port 993
- [ ] Rspamd is scanning mail (check `rspamc stat`)
- [ ] PostgreSQL has the ifinmail schema with seed data
- [ ] Python API is running and `/v1/docs` is accessible
- [ ] Webmail UI loads at `/` and shows the inbox
- [ ] Admin dashboard loads at `/admin` and shows DNS health
- [ ] DKIM signing is active (check outbound message headers)
- [ ] SPF and DMARC records are published in DNS (or documented for mock DNS)
- [ ] TLS is enabled (check `openssl s_client -connect localhost:993`)
- [ ] End-to-end test script passes all checks
- [ ] All `.ifinmail-*` CSS is prefixed correctly
- [ ] No React, Angular, Vue, or npm build step exists
- [ ] Git history is clean with meaningful commit messages
- [ ] README explains how to run the project

---

## Troubleshooting Guide

Common capstone issues and where to look:

| Symptom | Check |
|---|---|
| Mail not arriving | `sudo postqueue -p` — is it queued? Check `mail.log` for errors |
| IMAP login fails | `sudo doveadm user <email>` — does user exist? Check auth SQL |
| DKIM not verifying | `dig default._domainkey.<domain> TXT` — is the record correct? |
| API returns 500 | `sudo journalctl -u ifinmail-api -n 50` — check stack trace |
| Can't connect on port 587 | `sudo ufw status` — is the port open? `ss -tlnp \| grep 587` |
| Rspamd not scanning | `rspamc stat` — is it running? Check milter socket in Postfix |
| CSS looks wrong | Check browser DevTools — are `.ifinmail-*` classes applied? |

---

## Week 12 Resource Index

| Resource | Location |
|---|---|
| Capstone requirements | `CAPSTONE_REQUIREMENTS.md` |
| E2E test script | `code/capstone_e2e_test.py` |
| Demo flow script | `code/demo_flow.md` |
| Presentation template | `code/presentation_template.md` |
| Troubleshooting guide | `code/troubleshooting.md` |

---

## Congratulations

You have completed the 12-week ifinmail Engineering Curriculum. You started with Linux fundamentals and built a complete email platform. The skills you have acquired — mail infrastructure, API design, frontend development with minimal dependencies, security hardening, and DevOps — are directly applicable to the production ifinmail project.

The proposal describes six development phases. Your capstone implements Phase 1 (Foundation) and parts of Phase 2 (API Contract and Web Client). You know enough now to contribute to any part of the ifinmail codebase.

**Next steps after graduation:**

- Join the ifinmail development team
- Pick a specialization: mail infrastructure (Postfix/Rspamd), API/backend (Python/FastAPI), core libraries (Rust), frontend (vanilla JS/CSS), or mobile/desktop clients (Kotlin/Swift/Rust)
- Continue deepening your knowledge in your chosen area
- Help build the next phases: reputation controls, Android client, desktop clients, scale and business features

---

## Full Curriculum Index

| Week | Topic | Directory |
|---|---|---|
| 1 | Linux/Unix Fundamentals | [`week_01/`](../week_01/) |
| 2 | Networking & Email Protocols | [`week_02/`](../week_02/) |
| 3 | Python, Git & Dev Environment | [`week_03/`](../week_03/) |
| 4 | Databases & Data Modeling | [`week_04/`](../week_04/) |
| 5 | Postfix & SMTP | [`week_05/`](../week_05/) |
| 6 | Dovecot & IMAP | [`week_06/`](../week_06/) |
| 7 | Email Security & Authentication | [`week_07/`](../week_07/) |
| 8 | Python API Development | [`week_08/`](../week_08/) |
| 9 | Rust Fundamentals | [`week_09/`](../week_09/) |
| 10 | Minimal Frontend | [`week_10/`](../week_10/) |
| 11 | Security, DevOps & Deployment | [`week_11/`](../week_11/) |
| 12 | Capstone Project | [`week_12/`](../week_12/) |

---

*Week 12 of 12 — Capstone Project for ifinmail Platform Engineering*

*End of ifinmail Engineering Curriculum. Thank you for your dedication.*

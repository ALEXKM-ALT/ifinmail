# Week 5: Postfix & SMTP Configuration

**Month 2: Core Mail Stack | Days 25–30**

Postfix is the SMTP engine of ifinmail App — it receives, routes, and delivers every message. This week covers installation, core configuration, virtual domains, TLS, and the integration patterns that connect Postfix to the rest of the platform.

---

## Learning Goals for the Week

By Sunday, you will be able to:

- Install and configure Postfix for a test domain
- Understand `main.cf` and `master.cf` and make safe changes
- Set up virtual domains and virtual mailboxes
- Configure TLS for inbound and outbound SMTP
- Read and interpret Postfix logs to diagnose delivery issues
- Understand how Postfix integrates with Dovecot (LMTP), Rspamd (policy), and PostgreSQL (maps)

---

## Day 1 (Monday): Postfix Installation & First Configuration

### Learning Objectives
- Install Postfix on a development server
- Understand the two key configuration files: `main.cf` and `master.cf`
- Configure a basic internet-site Postfix
- Use `postconf` to inspect and modify configuration
- Send a test email locally

### Theory / Reading
- **Postfix architecture**: master daemon + multiple service daemons (smtpd, qmgr, lmtp, cleanup, etc.)
- **main.cf**: global configuration parameters
- **master.cf**: service definitions (which daemons run, how, and as whom)
- **postconf**: the safe way to view and edit Postfix config (`postconf -n` for non-defaults)

### Practical Exercise
```bash
# Install Postfix (Ubuntu/Debian)
sudo apt update
sudo DEBIAN_FRONTEND=noninteractive apt install -y postfix postfix-doc

# Choose "Internet Site" when prompted, or set non-interactively:
# sudo debconf-set-selections <<< "postfix postfix/mailname string mail.ifinmail.local"
# sudo debconf-set-selections <<< "postfix postfix/main_mailer_type string 'Internet Site'"

# Verify installation
postconf -n | head -20                    # Non-default settings
sudo systemctl status postfix
which postconf

# Key directories
ls /etc/postfix/                          # Configuration files
ls /var/spool/postfix/                    # Queue directories
ls /var/log/mail.log                      # Mail log

# Read the default main.cf (with comments)
head -100 /etc/postfix/main.cf
```

```bash
# First configuration: set basic parameters
sudo postconf -e "myhostname = mail.ifinmail.local"
sudo postconf -e "mydomain = ifinmail.local"
sudo postconf -e "myorigin = /etc/mailname"
sudo postconf -e "inet_interfaces = loopback-only"
sudo postconf -e "mydestination = \$myhostname, localhost.\$mydomain, localhost"

# View what we changed
postconf myhostname mydomain myorigin inet_interfaces mydestination

# Restart to apply
sudo systemctl restart postfix

# Send a local test email
echo "This is a test email from ifinmail training." | mail -s "Week 5 Test" $USER

# Check the logs
sudo tail -20 /var/log/mail.log

# Check local mail
mail   # or: cat /var/mail/$USER
```

### Checkpoint Questions
1. What is the difference between `main.cf` and `master.cf`?
2. Why does `inet_interfaces = loopback-only` limit Postfix to local mail only? When would we change this?
3. What is `myorigin` and why does it matter?
4. Where does Postfix store queued messages on disk?

### Connection to ifinmail App
Postfix is the first component in the ifinmail architecture diagram (Section 4.1). Every message flows through it. The configuration you learn today — `myhostname`, `mydomain`, `inet_interfaces` — is the foundation you will extend with virtual domains, TLS, and Dovecot integration.

---

## Day 2 (Tuesday): Virtual Domains & Virtual Mailboxes

### Learning Objectives
- Understand virtual alias domains vs virtual mailbox domains
- Configure Postfix for virtual hosting (multiple domains)
- Use lookup tables (hash maps, eventually PostgreSQL maps)
- Understand the difference between local delivery and virtual delivery

### Theory / Reading
- **Virtual alias domains**: each address maps to a real email address elsewhere
- **Virtual mailbox domains**: each address has its own mailbox on this server
- **Lookup tables**: `hash:`, `ldap:`, `pgsql:`, `mysql:` — we will use `hash:` first, then `pgsql:` later
- **`virtual_mailbox_domains`**: domains for which Postfix accepts mail and delivers locally

### Practical Exercise
```bash
# Create virtual domain configuration
sudo mkdir -p /etc/postfix/virtual

# Define virtual domains
cat << 'EOF' | sudo tee /etc/postfix/virtual/virtual_domains
ifinmail.local     OK
eleso.local        OK
EOF

# Define virtual mailboxes (user → mailbox path)
cat << 'EOF' | sudo tee /etc/postfix/virtual/virtual_mailboxes
alice@ifinmail.local    ifinmail.local/alice/
bob@ifinmail.local      ifinmail.local/bob/
admin@eleso.local       eleso.local/admin/
EOF

# Define virtual aliases
cat << 'EOF' | sudo tee /etc/postfix/virtual/virtual_aliases
postmaster@ifinmail.local    alice@ifinmail.local
abuse@ifinmail.local         alice@ifinmail.local
info@eleso.local             admin@eleso.local
EOF

# Convert to Postfix lookup tables (hashed Berkeley DB)
sudo postmap /etc/postfix/virtual/virtual_domains
sudo postmap /etc/postfix/virtual/virtual_mailboxes
sudo postmap /etc/postfix/virtual/virtual_aliases

# Configure Postfix to use virtual domains
sudo postconf -e "virtual_mailbox_domains = hash:/etc/postfix/virtual/virtual_domains"
sudo postconf -e "virtual_mailbox_maps = hash:/etc/postfix/virtual/virtual_mailboxes"
sudo postconf -e "virtual_alias_maps = hash:/etc/postfix/virtual/virtual_aliases"
sudo postconf -e "virtual_mailbox_base = /var/mail/vhosts"

# Create the mailbox directory
sudo mkdir -p /var/mail/vhosts
sudo chown -R postfix:postfix /var/mail/vhosts

# Verify configuration
postconf virtual_mailbox_domains virtual_mailbox_maps virtual_alias_maps virtual_mailbox_base

# Test the virtual maps
postmap -q "alice@ifinmail.local" /etc/postfix/virtual/virtual_mailboxes
postmap -q "info@eleso.local" /etc/postfix/virtual/virtual_aliases

# Reload Postfix
sudo systemctl reload postfix

# Check logs for errors
sudo journalctl -u postfix -n 20
```

### Checkpoint Questions
1. What is the difference between a virtual alias and a virtual mailbox?
2. Why do we use `postmap` on text files? What does it generate?
3. How would you add a third domain `acme.local` with a mailbox `carol@acme.local`?
4. Why is `virtual_mailbox_base` separated from the lookup table?

### Connection to ifinmail App
The proposal envisions hosting many domains on one platform. Virtual domains are how Postfix handles `eleso.com`, `acme.com`, `ifinsta.io`, and every customer domain. In production, these maps will come from PostgreSQL (via `pgsql:` tables), not flat files.

---

## Day 3 (Wednesday): Postfix Queues & Transport

### Learning Objectives
- Understand Postfix queue directories (incoming, active, deferred, hold, corrupt)
- Inspect and manage the mail queue with `postqueue` and `postsuper`
- Configure transport maps for routing decisions
- Understand the queue manager (qmgr) lifecycle
- Simulate delivery to Dovecot via LMTP

### Theory / Reading
- **Queue lifecycle**: incoming → active → (delivered | deferred)
- **deferred queue**: temporary failures; Postfix retries with exponential backoff
- **bounce/NDR**: non-delivery report when a message can't be delivered
- **qmgr**: the queue manager daemon that schedules deliveries

### Practical Exercise
```bash
# Inspect the queue
sudo postqueue -p                    # List all queued mail
sudo mailq                           # Same as postqueue -p

# Queue directories
ls -la /var/spool/postfix/
ls -la /var/spool/postfix/active/
ls -la /var/spool/postfix/deferred/
ls -la /var/spool/postfix/incoming/

# Check queue sizes
find /var/spool/postfix/active -type f | wc -l
find /var/spool/postfix/deferred -type f | wc -l

# Flush the queue (retry all deferred)
sudo postqueue -f

# Delete a specific message from the queue
# sudo postsuper -d <queue-id>

# Hold and release messages
# sudo postsuper -h <queue-id>   # Hold
# sudo postsuper -H <queue-id>   # Release

# --- Transport Maps ---
cat << 'EOF' | sudo tee /etc/postfix/virtual/transport
ifinmail.local    lmtp:unix:private/dovecot-lmtp
eleso.local       lmtp:unix:private/dovecot-lmtp
EOF
sudo postmap /etc/postfix/virtual/transport

sudo postconf -e "transport_maps = hash:/etc/postfix/virtual/transport"
sudo postconf -e "virtual_transport = lmtp:unix:private/dovecot-lmtp"

sudo systemctl reload postfix
```

### Checkpoint Questions
1. What causes a message to move from "active" to "deferred"?
2. How often does Postfix retry deferred messages by default?
3. What does `lmtp:unix:private/dovecot-lmtp` mean? What is LMTP?
4. Why separate the transport for different domains?

### Connection to ifinmail App
The queue is where deliverability lives or dies. Section 6.3 (warm-up strategy) depends on controlling queue rates. The transport map is how Postfix hands mail to Dovecot's LMTP for final delivery — the critical Postfix→Dovecot integration.

---

## Day 4 (Thursday): TLS Configuration for Postfix

### Learning Objectives
- Generate or obtain TLS certificates for Postfix
- Configure opportunistic and mandatory TLS
- Understand the difference between port 25, 465, and 587 TLS settings
- Test TLS configuration with `openssl s_client`

### Theory / Reading
- **Opportunistic TLS**: use TLS if the other side supports it (port 25)
- **Mandatory TLS**: require TLS, reject if unavailable (submission on 587, SMTPS on 465)
- **Certificate files**: public cert, private key, chain file (intermediate CAs)
- **Proposal Section 13.3**: "TLS everywhere" with MTA-STS and TLS-RPT

### Practical Exercise
```bash
# Create self-signed certificate for testing (production uses Certbot/Let's Encrypt)
sudo mkdir -p /etc/postfix/certs
sudo openssl req -new -x509 -days 365 -nodes \
    -newkey rsa:2048 \
    -keyout /etc/postfix/certs/mail.ifinmail.local.key \
    -out /etc/postfix/certs/mail.ifinmail.local.crt \
    -subj "/CN=mail.ifinmail.local"

sudo chmod 640 /etc/postfix/certs/mail.ifinmail.local.key
sudo chown root:postfix /etc/postfix/certs/mail.ifinmail.local.key
```

```bash
# Configure TLS in main.cf
sudo postconf -e "smtpd_tls_cert_file = /etc/postfix/certs/mail.ifinmail.local.crt"
sudo postconf -e "smtpd_tls_key_file = /etc/postfix/certs/mail.ifinmail.local.key"

# Port 25: opportunistic TLS (receive from other servers)
sudo postconf -e "smtpd_tls_security_level = may"
sudo postconf -e "smtpd_tls_protocols = >=TLSv1.2"
sudo postconf -e "smtpd_tls_mandatory_protocols = >=TLSv1.2"
sudo postconf -e "smtpd_tls_ciphers = high"
sudo postconf -e "smtpd_tls_mandatory_ciphers = high"

# Outbound TLS: use it when available
sudo postconf -e "smtp_tls_security_level = may"
sudo postconf -e "smtp_tls_protocols = >=TLSv1.2"
sudo postconf -e "smtp_tls_ciphers = high"

# Enable TLS logging
sudo postconf -e "smtpd_tls_received_header = yes"
sudo postconf -e "smtpd_tls_loglevel = 1"
sudo postconf -e "smtp_tls_loglevel = 1"

# Reload and test
sudo systemctl reload postfix

# Test TLS on port 25 (STARTTLS)
echo "Q" | openssl s_client -connect localhost:25 -starttls smtp 2>/dev/null | grep -E "subject=|issuer=|Verify return code"

# Review TLS configuration
postconf | grep -E "_tls_" | sort
```

### Checkpoint Questions
1. What is the difference between `smtpd_tls_security_level = may` and `= encrypt`?
2. Why use different TLS settings for port 25 vs port 587?
3. What does `smtpd_tls_received_header = yes` add to each message?
4. How does MTA-STS (proposal Section 5.4) improve on opportunistic TLS?

### Connection to ifinmail App
TLS is the first line of transport security. Every connection to ifinmail's Postfix must be encrypted. In production, Certbot will auto-renew certificates. The `smtp_tls` settings also apply to outbound delivery — protecting mail sent to other servers that support TLS.

---

## Day 5 (Friday): Postfix + PostgreSQL Integration & Log Analysis

### Learning Objectives
- Configure Postfix to read virtual maps from PostgreSQL
- Understand the SQL query format for Postfix lookup tables
- Analyze Postfix logs to troubleshoot delivery
- Set up log-based monitoring for the deliverability dashboard

### Theory / Reading
- **Postfix pgsql maps**: queries that return a single value for Postfix to use
- **Connection pooling**: Postfix caches database connections; `hosts` lists servers
- **Log format**: each Postfix daemon logs with its PID and queue ID for tracing
- **Proposal Section 14.3**: monitor SMTP queue length, delivery failures, bounce rates

### Practical Exercise
```bash
# Create PostgreSQL user for Postfix
sudo -u postgres psql << 'EOF'
CREATE USER postfix WITH PASSWORD 'postfix_pass';
GRANT CONNECT ON DATABASE ifinmail TO postfix;
GRANT USAGE ON SCHEMA ifinmail TO postfix;
GRANT SELECT ON ifinmail.domains TO postfix;
GRANT SELECT ON ifinmail.mailboxes TO postfix;
GRANT SELECT ON ifinmail.aliases TO postfix;
EOF

# Create Postfix → PostgreSQL map files
sudo mkdir -p /etc/postfix/pgsql

# Virtual domains query
cat << 'EOF' | sudo tee /etc/postfix/pgsql/virtual_domains.cf
user = postfix
password = postfix_pass
hosts = localhost
dbname = ifinmail
query = SELECT name FROM ifinmail.domains WHERE name = '%s' AND verified = TRUE
EOF

# Virtual mailboxes query
cat << 'EOF' | sudo tee /etc/postfix/pgsql/virtual_mailboxes.cf
user = postfix
password = postfix_pass
hosts = localhost
dbname = ifinmail
query = SELECT local_part||'@'||(SELECT name FROM ifinmail.domains WHERE id = domain_id)||'/'||local_part||'/' FROM ifinmail.mailboxes WHERE local_part = '%u' AND domain_id = (SELECT id FROM ifinmail.domains WHERE name = '%d')
EOF

# Virtual aliases query
cat << 'EOF' | sudo tee /etc/postfix/pgsql/virtual_aliases.cf
user = postfix
password = postfix_pass
hosts = localhost
dbname = ifinmail
query = SELECT destination FROM ifinmail.aliases WHERE source = '%u' AND domain_id = (SELECT id FROM ifinmail.domains WHERE name = '%d')
EOF

# Secure the password files
sudo chmod 640 /etc/postfix/pgsql/*.cf
sudo chown root:postfix /etc/postfix/pgsql/*.cf

# Switch to PostgreSQL maps (comment out hash maps first!)
sudo postconf -e "virtual_mailbox_domains = pgsql:/etc/postfix/pgsql/virtual_domains.cf"
sudo postconf -e "virtual_mailbox_maps = pgsql:/etc/postfix/pgsql/virtual_mailboxes.cf"
sudo postconf -e "virtual_alias_maps = pgsql:/etc/postfix/pgsql/virtual_aliases.cf"

sudo systemctl reload postfix
```

```bash
# --- Log Analysis (critical skill for mail operations) ---
# Find all deliveries today
sudo grep "$(date +%b\ %d)" /var/log/mail.log | grep "status=sent" | head -10

# Find all rejections
sudo grep "$(date +%b\ %d)" /var/log/mail.log | grep "reject" | head -10

# Trace a specific queue ID through the system
# sudo grep "QUEUE_ID" /var/log/mail.log

# Count deliveries by domain
sudo grep "status=sent" /var/log/mail.log | grep -oP 'to=<\K[^>]+' | awk -F@ '{print $2}' | sort | uniq -c | sort -rn

# Find deferred messages
sudo grep "status=deferred" /var/log/mail.log | tail -10

# Monitor the queue (run periodically)
echo "=== Queue Status ==="
sudo postqueue -p | tail -1
echo "=== Deferred Reasons ==="
sudo grep "status=deferred" /var/log/mail.log | grep -oP 'dsn=\K[^,]+' | sort | uniq -c
```

### Checkpoint Questions
1. Why is `verified = TRUE` in the domains query? What security property does it enforce?
2. How does Postfix's `%s`, `%u`, `%d` substitution work in SQL queries?
3. What does the deferred queue tell you about your mail system's health?
4. How would you detect a spam outbreak from the logs?

### Connection to ifinmail App
This is production ifinmail: Postfix reading domains, mailboxes, and aliases directly from PostgreSQL. The admin dashboard will run these same log queries to populate the deliverability dashboard (proposal Section 6.5).

---

## Day 6 (Saturday): Review & Integration

### Review Challenge: Postfix Health Monitor Script

Write a script `~/ifinmail-scripts/postfix_health.sh` that:

1. Reports Postfix service status
2. Shows queue counts (active, deferred, total)
3. Lists top 5 domains by delivery count today
4. Shows rejection count and top rejection reasons
5. Checks TLS certificate expiry date
6. Verifies PostgreSQL map connectivity
7. Outputs a single-page summary (text) suitable for the admin dashboard

**Stretch goal**: Add a `--watch` mode that refreshes every 30 seconds (like `top` for Postfix).

### Week 5 Self-Assessment

Before moving to Week 6, confirm you can:
- [ ] Install and configure Postfix from scratch
- [ ] Set up virtual domains and mailboxes with lookup tables
- [ ] Explain the Postfix queue lifecycle
- [ ] Configure TLS for inbound and outbound mail
- [ ] Connect Postfix to PostgreSQL for virtual maps
- [ ] Analyze Postfix logs to diagnose delivery issues
- [ ] Use `postconf`, `postqueue`, `postsuper`, and `postmap` fluently

---

## Week 5 Resource Index

| Resource | Location |
|---|---|
| Postfix `main.cf` reference | `references/postfix_main_cf.md` |
| Postfix `master.cf` reference | `references/postfix_master_cf.md` |
| Virtual hosting guide | `references/postfix_virtual.md` |
| PostgreSQL map queries | `references/postfix_pgsql_queries.md` |
| Log analysis cheat sheet | `references/postfix_logs.md` |
| TLS setup checklist | `references/postfix_tls.md` |

---

*Week 5 of 12 — Postfix & SMTP for ifinmail Platform Engineering*

# Week 6: Dovecot & IMAP

**Month 2: Core Mail Stack | Days 31–36**

Dovecot provides IMAP access, LMTP delivery, and mailbox storage for ifinmail. It serves traditional email clients (Thunderbird, Outlook, Apple Mail) while the ifinmail API serves official apps — both reading the same Maildir storage. This week covers installation, authentication, LMTP integration with Postfix, and Sieve filtering.

---

## Learning Goals for the Week

By Sunday, you will be able to:

- Install and configure Dovecot for IMAP and LMTP
- Set up Maildir storage and understand quota management
- Connect Dovecot authentication to PostgreSQL
- Integrate Dovecot LMTP with Postfix for final delivery
- Configure Sieve for server-side mail filtering
- Test IMAP connectivity with `openssl s_client`

---

## Day 1 (Monday): Dovecot Installation & Maildir Storage

### Learning Objectives
- Install Dovecot and understand its component services
- Understand Maildir vs mbox storage formats
- Configure basic Dovecot for local mail delivery
- Test IMAP login and mailbox access

### Theory / Reading
- **Dovecot services**: imap, imap-login, lmtp, auth, indexer, replicator
- **Maildir**: one file per message, directories for folders — the standard for modern mail
- **mbox**: single file per folder — legacy, not suitable for ifinmail
- **Config layout**: `/etc/dovecot/dovecot.conf` + `conf.d/*.conf` modular includes

### Practical Exercise
```bash
# Install Dovecot
sudo apt update && sudo apt install -y dovecot-core dovecot-imapd dovecot-lmtpd

# Verify installation
dovecot --version
sudo systemctl status dovecot
ls /etc/dovecot/
ls /etc/dovecot/conf.d/

# Create the vmail user (common owner for all virtual mailboxes)
sudo groupadd -g 5000 vmail
sudo useradd -g vmail -u 5000 -d /var/mail/vhosts -m -s /usr/sbin/nologin vmail
sudo chown -R vmail:vmail /var/mail/vhosts
```

```bash
# Configure Dovecot for Maildir
# Edit /etc/dovecot/conf.d/10-mail.conf
sudo sed -i 's|^#\?mail_location = .*|mail_location = maildir:/var/mail/vhosts/%d/%n|' /etc/dovecot/conf.d/10-mail.conf

# Verify the setting
grep "^mail_location" /etc/dovecot/conf.d/10-mail.conf

# Set mail privileges
sudo sed -i 's/^#\?mail_uid = .*/mail_uid = vmail/' /etc/dovecot/conf.d/10-mail.conf
sudo sed -i 's/^#\?mail_gid = .*/mail_gid = vmail/' /etc/dovecot/conf.d/10-mail.conf

# Enable IMAP service
sudo sed -i 's/^#\?protocols = .*/protocols = imap lmtp/' /etc/dovecot/dovecot.conf

# Configure IMAP listener
cat << 'EOF' | sudo tee /etc/dovecot/conf.d/10-master.conf
service imap-login {
  inet_listener imap {
    port = 143
  }
  inet_listener imaps {
    port = 993
    ssl = yes
  }
}

service lmtp {
  unix_listener /var/spool/postfix/private/dovecot-lmtp {
    mode = 0600
    user = postfix
    group = postfix
  }
}

service auth {
  unix_listener /var/spool/postfix/private/auth {
    mode = 0666
    user = postfix
    group = postfix
  }
  
  unix_listener auth-userdb {
    mode = 0600
    user = vmail
  }
}
EOF

# Create a test mailbox directory
sudo mkdir -p /var/mail/vhosts/ifinmail.local/alice/{cur,new,tmp}
sudo chown -R vmail:vmail /var/mail/vhosts/ifinmail.local

# Restart Dovecot
sudo systemctl restart dovecot
sudo systemctl status dovecot

# Test IMAP connection
printf "a1 LOGIN alice@ifinmail.local password123\na2 LIST \"\" \"*\"\na3 LOGOUT\n" | nc -w 5 localhost 143
```

### Checkpoint Questions
1. Why is Maildir preferred over mbox for ifinmail?
2. What does the `%d/%n` format in `mail_location` expand to?
3. Why does LMTP need a Unix socket that Postfix can write to?
4. What is the purpose of the `vmail` user?

### Connection to ifinmail
Dovecot is the MDA and IMAP server. The `mail_location` format maps directly to the virtual mailbox structure we set up in Week 5. Both Postfix (via LMTP) and the ifinmail API (via direct file access or Dovecot's API) read from the same Maildir.

---

## Day 2 (Tuesday): Dovecot Authentication & PostgreSQL Integration

### Learning Objectives
- Understand Dovecot's authentication architecture (passdb, userdb)
- Configure SASL authentication for Postfix submission
- Connect Dovecot to PostgreSQL for user authentication
- Generate and verify password hashes

### Theory / Reading
- **passdb**: tells Dovecot HOW to verify a password (SQL, LDAP, passwd-file, PAM)
- **userdb**: tells Dovecot WHERE the user's mail is and what their settings are
- **SASL**: Simple Authentication and Security Layer — Postfix uses Dovecot SASL for submission auth
- **Argon2id**: the password hashing algorithm mandated in proposal Section 13.1

### Practical Exercise
```sql
-- Add a password column to users (in psql)
ALTER TABLE ifinmail.users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);

-- Generate an Argon2id hash (we will do it in Python later; placeholder for now)
UPDATE ifinmail.users SET password_hash = '{ARGON2ID}$argon2id$v=19$m=65536,t=3,p=4$hash_here'
WHERE email = 'alice@eleso.com';
```

```bash
# Create Dovecot SQL configuration
sudo mkdir -p /etc/dovecot/dovecot-sql.conf.ext.d

cat << 'EOF' | sudo tee /etc/dovecot/dovecot-sql.conf.ext
driver = pgsql
connect = host=localhost dbname=ifinmail user=dovecot password=dovecot_pass
default_pass_scheme = ARGON2ID

# Password query: returns password hash for authentication
password_query = \
    SELECT email AS user, password_hash AS password, \
           'vmail' AS userdb_uid, 'vmail' AS userdb_gid, \
           '/var/mail/vhosts/%d/%n' AS userdb_home, \
           'maildir:/var/mail/vhosts/%d/%n' AS userdb_mail \
    FROM ifinmail.users \
    WHERE email = '%u' AND is_active = TRUE

# User query: returns user info after authentication
user_query = \
    SELECT '/var/mail/vhosts/%d/%n' AS home, \
           'maildir:/var/mail/vhosts/%d/%n' AS mail, \
           5000 AS uid, 5000 AS gid \
    FROM ifinmail.users \
    WHERE email = '%u' AND is_active = TRUE

# Iterate over all users (for doveadm commands)
iterate_query = SELECT email AS user FROM ifinmail.users WHERE is_active = TRUE
EOF

sudo chmod 640 /etc/dovecot/dovecot-sql.conf.ext
sudo chown root:dovecot /etc/dovecot/dovecot-sql.conf.ext
```

```bash
# Create Dovecot PostgreSQL user
sudo -u postgres psql << 'EOF'
CREATE USER dovecot WITH PASSWORD 'dovecot_pass';
GRANT CONNECT ON DATABASE ifinmail TO dovecot;
GRANT USAGE ON SCHEMA ifinmail TO dovecot;
GRANT SELECT ON ifinmail.users TO dovecot;
EOF

# Configure Dovecot auth to use SQL
cat << 'EOF' | sudo tee /etc/dovecot/conf.d/auth-sql.conf.ext
passdb {
  driver = sql
  args = /etc/dovecot/dovecot-sql.conf.ext
}

userdb {
  driver = sql
  args = /etc/dovecot/dovecot-sql.conf.ext
}
EOF

# Enable auth-sql in the main config
grep -q "!include auth-sql.conf.ext" /etc/dovecot/conf.d/10-auth.conf || \
    echo '!include auth-sql.conf.ext' | sudo tee -a /etc/dovecot/conf.d/10-auth.conf

sudo systemctl restart dovecot
sudo tail -20 /var/log/mail.log | grep dovecot
```

### Checkpoint Questions
1. What is the difference between passdb and userdb in Dovecot?
2. Why does the SQL query include `is_active = TRUE`? What security purpose does it serve?
3. How does Postfix use Dovecot's SASL for submission authentication?
4. What information does userdb provide that passdb does not?

### Connection to ifinmail
Dovecot authentication is how both IMAP clients and Postfix submission (port 587) verify users. The SQL queries connect directly to the platform's PostgreSQL database — the same users table that the API uses. This is the centralized authentication model the proposal describes.

---

## Day 3 (Wednesday): Postfix ↔ Dovecot LMTP Integration

### Learning Objectives
- Understand the LMTP protocol and why it is used instead of pipe delivery
- Complete the Postfix-to-Dovecot delivery chain
- Configure Postfix to use Dovecot SASL for submission authentication
- Test the full send→receive flow end-to-end

### Theory / Reading
- **LMTP**: Local Mail Transfer Protocol — a simplified SMTP for final delivery
- **vs pipe**: LMTP gives per-recipient status; pipe is all-or-nothing
- **Submission service**: Postfix on port 587 with SASL auth and mandatory TLS
- **End-to-end flow**: SMTP (inbound) → Postfix → LMTP → Dovecot → Maildir

### Practical Exercise
```bash
# --- Step 1: Configure Postfix submission (port 587) with Dovecot SASL ---
sudo postconf -e "smtpd_sasl_type = dovecot"
sudo postconf -e "smtpd_sasl_path = private/auth"
sudo postconf -e "smtpd_sasl_auth_enable = yes"
sudo postconf -e "smtpd_sasl_security_options = noanonymous"
sudo postconf -e "smtpd_sasl_tls_security_options = noanonymous"
sudo postconf -e "smtpd_tls_auth_only = yes"

# Allow authenticated users to send mail
sudo postconf -e "smtpd_relay_restrictions = permit_mynetworks, permit_sasl_authenticated, defer_unauth_destination"

# --- Step 2: Configure LMTP in master.cf ---
# master.cf already has LMTP commented out; we enable it via transport already set up

# --- Step 3: Enable submission in master.cf ---
# Uncomment or add the submission service
grep -q "^submission" /etc/postfix/master.cf || cat << 'EOF' | sudo tee -a /etc/postfix/master.cf
submission inet n       -       y       -       -       smtpd
  -o syslog_name=postfix/submission
  -o smtpd_tls_security_level=encrypt
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_relay_restrictions=permit_sasl_authenticated,reject
  -o smtpd_recipient_restrictions=permit_sasl_authenticated,reject
  -o milter_macro_daemon_name=ORIGINATING
EOF

sudo systemctl reload postfix
sudo systemctl restart dovecot

# --- Step 4: Test the full flow ---
# Check Dovecot LMTP socket exists
ls -la /var/spool/postfix/private/dovecot-lmtp

# Check auth socket
ls -la /var/spool/postfix/private/auth

# Send a test email via submission (this will fail without real SASL creds,
# but it verifies the service is listening)
echo "Q" | openssl s_client -connect localhost:587 -starttls smtp 2>/dev/null | head -5

# Check logs for LMTP delivery attempts
sudo grep "lmtp" /var/log/mail.log | tail -10
```

### Checkpoint Questions
1. Why use LMTP (port 24/protocol) instead of Postfix's built-in `virtual` delivery agent?
2. What does `smtpd_tls_auth_only = yes` enforce?
3. How does `permit_sasl_authenticated` in relay_restrictions prevent open relay?
4. Why does the submission service in master.cf set different options than the main smtpd service?

### Connection to ifinmail
This is the complete delivery chain: Postfix receives mail on port 25, scans it (Rspamd in Week 7), and delivers it to Dovecot via LMTP. Users send mail on port 587 with SASL auth. This split (receive on 25, send on 587) is exactly how production mail systems work.

---

## Day 4 (Thursday): IMAP over TLS & Client Setup

### Learning Objectives
- Configure TLS certificates for Dovecot
- Understand IMAP over TLS (port 993) vs STARTTLS (port 143)
- Connect a mail client (Thunderbird or similar) to Dovecot
- Debug IMAP connection issues

### Theory / Reading
- **IMAPS**: IMAP over TLS on port 993 (implicit TLS, preferred)
- **IMAP + STARTTLS**: plain IMAP on port 143, upgrade to TLS after connection
- **Dovecot SSL config**: `/etc/dovecot/conf.d/10-ssl.conf`
- **Certificate sharing**: Dovecot and Postfix can use the same certificate

### Practical Exercise
```bash
# Share the Postfix certificate with Dovecot (or create a new one)
sudo mkdir -p /etc/dovecot/certs

# Copy or symlink the cert from Postfix
sudo cp /etc/postfix/certs/mail.ifinmail.local.key /etc/dovecot/certs/
sudo cp /etc/postfix/certs/mail.ifinmail.local.crt /etc/dovecot/certs/
sudo chown root:dovecot /etc/dovecot/certs/*.key
sudo chmod 640 /etc/dovecot/certs/*.key

# Configure Dovecot SSL
cat << 'EOF' | sudo tee /etc/dovecot/conf.d/10-ssl.conf
ssl = required
ssl_cert = </etc/dovecot/certs/mail.ifinmail.local.crt
ssl_key = </etc/dovecot/certs/mail.ifinmail.local.key
ssl_min_protocol = TLSv1.2
ssl_cipher_list = HIGH:!aNULL:!eNULL:!EXPORT:!DES:!MD5:!PSK:!RC4
ssl_prefer_server_ciphers = yes
EOF

sudo systemctl restart dovecot

# Test IMAPS
echo "Q" | openssl s_client -connect localhost:993 2>/dev/null | head -10

# More detailed IMAP test over TLS
printf "a1 LOGIN alice@ifinmail.local password123\na2 LIST \"\" \"*\"\na3 LOGOUT\n" | \
    openssl s_client -connect localhost:993 -quiet 2>/dev/null
```

```bash
# --- Debugging checklist ---
echo "=== Dovecot config check ==="
sudo doveconf -n | grep -E "ssl|mail_location|auth|listen"

echo "=== IMAP port check ==="
ss -tlnp | grep -E ":(143|993) "

echo "=== Dovecot processes ==="
ps aux | grep dovecot

echo "=== Recent Dovecot logs ==="
sudo journalctl -u dovecot -n 20
```

### Checkpoint Questions
1. Why is port 993 (implicit TLS) preferred over port 143 (STARTTLS)?
2. What does `ssl = required` enforce?
3. How would you troubleshoot an IMAP login failure? List 3 things to check.
4. Why should Postfix and Dovecot use the same TLS certificate?

### Connection to ifinmail
Dovecot serves IMAP to traditional clients. The ifinmail API reads the same Maildir storage. This dual-access is crucial: users can use Thunderbird today and the official ifinmail app tomorrow, seeing the same inbox. TLS on IMAP is mandatory per the proposal's "TLS everywhere" principle.

---

## Day 5 (Friday): Sieve Filtering & doveadm Tools

### Learning Objectives
- Understand Sieve: server-side mail filtering language
- Write Sieve rules for sorting, flagging, and vacation auto-replies
- Use `doveadm` for mailbox management and troubleshooting
- Understand quotas and how they relate to the trust-level system

### Theory / Reading
- **Sieve**: RFC 5228; server-side filtering — runs during LMTP delivery
- **Common Sieve actions**: fileinto, redirect, discard, reject, vacation, addflag
- **doveadm**: the Dovecot administration tool — mailboxes, users, stats, replication
- **Quotas**: Maildir++ quota backend; proposal mentions quota support in Section 5.2

### Practical Exercise
```bash
# Install Sieve plugin
sudo apt install -y dovecot-sieve dovecot-managesieved

# Enable Sieve in Dovecot
cat << 'EOF' | sudo tee /etc/dovecot/conf.d/90-sieve.conf
plugin {
  sieve = file:~/sieve;active=~/.dovecot.sieve
  sieve_before = /etc/dovecot/sieve/before.d/
  sieve_after = /etc/dovecot/sieve/after.d/
  sieve_max_script_size = 1M
  sieve_max_actions = 32
}

protocol lmtp {
  mail_plugins = $mail_plugins sieve
}
EOF

sudo mkdir -p /etc/dovecot/sieve/{before.d,after.d}
```

```sieve
# Example: Global before-script for spam filtering
sudo tee /etc/dovecot/sieve/before.d/00-spam.sieve << 'EOF'
require ["fileinto", "envelope"];

# Move mail flagged as spam by Rspamd to the Junk folder
if header :contains "X-Spam" "Yes" {
    fileinto "Junk";
    stop;
}
EOF

# Compile the Sieve script (must be compiled for Dovecot)
sudo sievec /etc/dovecot/sieve/before.d/00-spam.sieve
```

```sieve
# Example: Per-user Sieve filter (goes in user's Maildir)
cat << 'EOF' > /tmp/user_sieve_example.sieve
require ["fileinto", "vacation", "variables"];

# Sort mailing lists into folders
if header :contains "List-Id" "ifinmail-dev" {
    fileinto "Lists.ifinmail-dev";
    stop;
}

# Auto-reply for vacation
if header :contains "subject" "Urgent" {
    vacation :days 1 :subject "Out of office" 
        "I am currently away and will respond when I return.";
}
EOF
```

```bash
# --- doveadm: the Dovecot administration Swiss Army knife ---
# List users
sudo doveadm user '*'

# Show user info
sudo doveadm user alice@ifinmail.local

# List mailboxes for a user
sudo doveadm mailbox list -u alice@ifinmail.local

# Show mailbox status (messages, size)
sudo doveadm mailbox status -u alice@ifinmail.local all INBOX

# Search for messages
sudo doveadm search -u alice@ifinmail.local ALL

# Fetch message metadata
sudo doveadm fetch -u alice@ifinmail.local "mailbox guid subject" ALL

# Rebuild mailbox indexes
# sudo doveadm force-resync -u alice@ifinmail.local INBOX

# Quota check
sudo doveadm quota get -u alice@ifinmail.local

# Stats
sudo doveadm stats dump
```

### Checkpoint Questions
1. What is the difference between `sieve_before` and `sieve_after`?
2. How does Sieve relate to Rspamd spam filtering (preview of Week 7)?
3. What does `doveadm force-resync` do and when would you use it?
4. How do quotas support the proposal's storage growth risk mitigation?

### Connection to ifinmail
Sieve is the server-side filtering engine. The ifinmail API can manage Sieve scripts, letting users create rules (move to folder, auto-reply, forward) that run during delivery. `doveadm` is the operational tool for mailbox management — the admin dashboard will use equivalent API calls.

---

## Day 6 (Saturday): Review & Integration

### Review Challenge: End-to-End Delivery Test

Set up a complete delivery test:

1. Use `swaks` (Swiss Army Knife for SMTP) to send a test email through Postfix submission (port 587)
2. Trace the message through Postfix logs → LMTP → Dovecot
3. Verify the message appears in the correct Maildir
4. Read the message via IMAP
5. Write a script that automates this test and reports PASS/FAIL for each stage

**Stretch goal**: Add a Sieve rule that files messages from a specific sender into a folder, then verify it works.

### Week 6 Self-Assessment

Before moving to Week 7, confirm you can:
- [ ] Install and configure Dovecot with Maildir storage
- [ ] Connect Dovecot authentication to PostgreSQL
- [ ] Integrate Postfix LMTP delivery with Dovecot
- [ ] Configure TLS for IMAP and submission
- [ ] Write and compile Sieve filter rules
- [ ] Use `doveadm` for user and mailbox management
- [ ] Trace a message through the full Postfix→Dovecot chain

---

## Week 6 Resource Index

| Resource | Location |
|---|---|
| Dovecot config reference | `references/dovecot_config.md` |
| SQL auth setup | `references/dovecot_sql_auth.md` |
| Postfix-Dovecot integration | `references/postfix_dovecot_lmtp.md` |
| Sieve language guide | `references/sieve_basics.md` |
| doveadm command reference | `references/doveadm_cheatsheet.md` |
| End-to-end test script | `challenges/week_06_e2e_test.md` |

---

*Week 6 of 12 — Dovecot & IMAP for ifinmail Platform Engineering*

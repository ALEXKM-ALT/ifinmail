# Week 7: Email Security — SPF, DKIM, DMARC & Rspamd

**Month 2: Core Mail Stack | Days 37–42**

Email authentication is what separates delivered mail from spam. This week covers the three pillars of email authentication (SPF, DKIM, DMARC), the Rspamd filtering and policy engine, and DNS-based reputation records. Without this layer, even a perfectly configured Postfix + Dovecot stack will send mail straight to the spam folder.

---

## Learning Goals for the Week

By Sunday, you will be able to:

- Create and validate SPF, DKIM, and DMARC DNS records
- Install and configure Rspamd for spam filtering, DKIM signing, and DMARC evaluation
- Understand how Rspamd integrates with Postfix via milter or policy service
- Implement the reputation scoring and trust level system from the proposal
- Build the deliverability dashboard DNS health checks
- Set up TLS-RPT and MTA-STS records

---

## Day 1 (Monday): SPF — Sender Policy Framework

### Learning Objectives
- Understand SPF: how it works and why it matters
- Write and analyze SPF records
- Configure Postfix to CHECK SPF on inbound mail
- Understand SPF alignment vs passing
- Debug SPF failures with `dig` and mail headers

### Theory / Reading
- **SPF**: the domain owner lists which IPs can send mail for the domain
- **Record format**: `v=spf1 ip4:192.0.2.1 include:_spf.google.com -all`
- **Qualifiers**: `+` pass, `-` fail (hardfail), `~` softfail, `?` neutral
- **SPF check**: Postfix/rspamd verifies the connecting IP against the sender domain's SPF record
- **Limitations**: SPF checks the envelope MAIL FROM, not the From: header; breaks with forwarding

### Practical Exercise
```bash
# Query real SPF records
dig gmail.com TXT +short | grep spf
dig outlook.com TXT +short | grep spf
dig proton.me TXT +short | grep spf

# Analyze these records
cat << 'EOF'
SPF Record Anatomy:
  v=spf1             - Version
  mx                  - Allow the domain's MX servers
  include:mechanism   - Include another domain's SPF
  ip4:192.0.2.0/24    - Allow this IPv4 range
  ip6:2001:db8::/32   - Allow this IPv6 range
  -all                - HARD FAIL: reject everything else
  ~all                - SOFT FAIL: accept but mark suspicious
  ?all                - NEUTRAL: no assertion
EOF

# Build the SPF record for ifinmail.local
echo "Proposed SPF for ifinmail.local:"
echo "  v=spf1 mx ip4:<YOUR_SERVER_IP> -all"

# FOR TESTING ONLY: add SPF record to DNS
# (Production: manage via DNS provider API or admin dashboard)
```

```bash
# Configure Postfix to check SPF (via policy service or Rspamd)
# Postfix can use pypolicyd-spf or delegate to Rspamd
sudo apt install -y postfix-policyd-spf-python 2>/dev/null || echo "Will use Rspamd for SPF"

# Basic SPF policy config for Postfix
cat << 'EOF' | sudo tee /etc/postfix-policyd-spf-python/policyd-spf.conf
debugLevel = 1
TestOnly = 0
HELO_reject = SPF_Not_Pass
Mail_From_reject = Fail
PermError_reject = False
TempError_Defer = False
EOF

# Add to Postfix master.cf (if using policyd-spf separately)
# We will mostly use Rspamd for this (Day 3)

# Check SPF headers on a received message
grep -i "spf" /var/log/mail.log | head -10
```

### Checkpoint Questions
1. What happens when a domain uses `-all` vs `~all`? Which should ifinmail App domains use?
2. Why does SPF break email forwarding? What mitigates this?
3. What is the 10-DNS-lookup limit and how do you avoid hitting it?
4. How does the ifinmail App admin dashboard verify SPF records?

### Connection to ifinmail App
Proposal Sections 5.4 and 6.5 describe continuous DNS health checking. SPF is the first check. The admin dashboard must show "SPF alignment status" for every domain. Rspamd (Day 3-4) performs the actual SPF checks during inbound delivery.

---

## Day 2 (Tuesday): DKIM — DomainKeys Identified Mail

### Learning Objectives
- Understand DKIM: cryptographic signing of outbound mail
- Generate DKIM keys and publish DKIM DNS records
- Configure DKIM signing for outbound mail
- Verify DKIM signatures on inbound mail
- Understand DKIM selectors and key rotation

### Theory / Reading
- **DKIM**: the sending server signs each message with a private key; receivers verify with the public key in DNS
- **Selector**: a named key (e.g., `default`, `202405`, `google`) — allows multiple keys per domain
- **DNS record**: `selector._domainkey.example.com TXT v=DKIM1; k=rsa; p=BASE64_PUBLIC_KEY`
- **Canonicalization**: relaxed vs simple — how to normalize headers/body before signing
- **Key rotation**: generate new keys periodically; publish new DNS; keep old selector active until mail in flight is delivered

### Practical Exercise
```bash
# Generate DKIM keys
sudo mkdir -p /etc/dkim
cd /etc/dkim

# Generate a 2048-bit RSA key pair
sudo openssl genrsa -out default.ifinmail.local.key 2048
sudo openssl rsa -in default.ifinmail.local.key -pubout -out default.ifinmail.local.pub

# Set permissions (private key must be 600!)
sudo chmod 600 default.ifinmail.local.key
sudo chown root:root default.ifinmail.local.key

# View the public key (this goes in DNS)
echo "DKIM Public Key (base64-encoded, split into quoted strings for DNS):"
sudo cat default.ifinmail.local.pub | grep -v "^-" | tr -d '\n' | fold -w 64
echo ""

# Construct the DNS record
echo ""
echo "DNS TXT Record:"
echo "  Name:   default._domainkey.ifinmail.local"
echo "  Value:  v=DKIM1; k=rsa; p=<PUBLIC_KEY_ABOVE>"
echo ""
echo "Example of what it looks like:"
echo "  v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA..."
```

```bash
# Install OpenDKIM (or we'll use Rspamd's DKIM module in Day 3)
sudo apt install -y opendkim opendkim-tools 2>/dev/null || echo "Will use Rspamd for DKIM"

# Test the key
opendkim-testkey -d ifinmail.local -s default -k /etc/dkim/default.ifinmail.local.key -v 2>/dev/null || \
    echo "(Key test will fully work once DNS is published)"

# Verify DKIM on received mail
echo "Checking DKIM headers in logs..."
sudo grep "dkim" /var/log/mail.log | tail -10
```

### Checkpoint Questions
1. Why use a selector (`default`) in the DKIM DNS record instead of just the domain?
2. What should the private key permissions be? Why?
3. How does DKIM survive email forwarding when SPF does not?
4. What is the key rotation strategy? Why is it important?

### Connection to ifinmail App
Proposal Section 5.3 assigns DKIM signing to Rspamd. Every outbound ifinmail message must be DKIM-signed. The deliverability dashboard (Section 6.5) shows "DKIM signing status." Combined with SPF and DMARC, DKIM is how ifinmail builds domain reputation.

---

## Day 3 (Wednesday): DMARC & Rspamd Installation

### Learning Objectives
- Understand DMARC: policy layer on top of SPF and DKIM
- Write DMARC DNS records with reporting
- Install and configure Rspamd
- Understand Rspamd's architecture (workers, modules, symbols, scores)

### Theory / Reading
- **DMARC**: tells receivers what to do when SPF/DKIM fail (none, quarantine, reject)
- **Alignment**: SPF alignment (envelope from = header from) AND/OR DKIM alignment (d= domain = header from)
- **DMARC reports**: aggregate (rua) and forensic (ruf) — daily XML reports from receivers
- **Rspamd**: high-performance spam filtering system with Lua plugins; modules for DKIM, DMARC, SPF, antivirus, fuzzy hashing, rate limiting

### Practical Exercise
```bash
# Construct the DMARC record for ifinmail.local (FOR TESTING)
cat << 'EOF'
DMARC DNS Record:
  Name:   _dmarc.ifinmail.local
  Value:  v=DMARC1; p=quarantine; rua=mailto:dmarc@ifinmail.local; ruf=mailto:dmarc-forensic@ifinmail.local; pct=100; sp=quarantine; adkim=s; aspf=s

Tag explanations:
  v=DMARC1       - Version
  p=quarantine   - Policy: none / quarantine / reject
  rua=           - Aggregate report email
  ruf=           - Forensic/Failure report email
  pct=100        - Apply to 100% of messages
  sp=quarantine  - Subdomain policy
  adkim=s        - DKIM alignment: s=strict, r=relaxed
  aspf=s         - SPF alignment: s=strict, r=relaxed
EOF
```

```bash
# Install Rspamd
sudo apt update
sudo apt install -y rspamd redis-server

# Enable and start
sudo systemctl enable rspamd
sudo systemctl start rspamd
sudo systemctl status rspamd

# Rspamd directories
ls /etc/rspamd/
ls /etc/rspamd/local.d/        # Local overrides (do not edit modules.d/ directly)
ls /etc/rspamd/modules.d/      # Module configs (use local.d/ to override)

# Rspamd web interface (local only by default)
echo "Rspamd web UI: http://localhost:11334"
# In production: protect this behind firewall/VPN only

# Check Rspamd status
rspamc stat
rspamadm configtest
```

```bash
# Basic Rspamd configuration overrides
# Create local.d/ files to configure (never edit modules.d/ directly)

# Configure worker ports
cat << 'EOF' | sudo tee /etc/rspamd/local.d/worker-normal.inc
bind_socket = "localhost:11333"
EOF

cat << 'EOF' | sudo tee /etc/rspamd/local.d/worker-controller.inc
bind_socket = "localhost:11334"
secure_ip = "127.0.0.1"
password = "$2$hash_of_password"  # Generated with: rspamadm pw
EOF

# Set up Redis backend for Rspamd (Bayes, fuzzy hashes, rate limits)
cat << 'EOF' | sudo tee /etc/rspamd/local.d/redis.inc
servers = "127.0.0.1:6379"
EOF

sudo systemctl restart rspamd

# Test with a sample message
echo "Subject: Test message" | rspamc -h localhost:11333
```

### Checkpoint Questions
1. What is the difference between DMARC `p=none`, `p=quarantine`, and `p=reject`? Which policy should a new domain start with?
2. What is DMARC alignment? Why can SPF pass but DMARC fail?
3. Why does Rspamd use Redis? What does it store there?
4. Why configure Rspamd in `local.d/` instead of editing `modules.d/` directly?

### Connection to ifinmail App
The proposal describes Rspamd as "a core component of deliverability and reputation management, not just a spam filter." DMARC is how you tell the world "reject mail that isn't from us." The Rspamd web UI becomes the foundation of the deliverability dashboard.

---

## Day 4 (Thursday): Rspamd DKIM Signing & Postfix Integration

### Learning Objectives
- Configure Rspamd to sign outbound mail with DKIM
- Integrate Rspamd with Postfix via milter protocol
- Set up Rspamd SPF, DKIM, and DMARC modules
- Configure spam scoring thresholds and actions

### Theory / Reading
- **Milter**: Mail Filter protocol — Postfix connects to Rspamd during SMTP transaction
- **Rspamd actions**: `no action`, `greylist`, `add header`, `rewrite subject`, `reject`
- **Symbols**: individual rules in Rspamd; each contributes to the spam score
- **Thresholds**: score thresholds for each action (e.g., reject at 15.0)

### Practical Exercise
```bash
# --- Step 1: DKIM signing configuration ---
sudo mkdir -p /etc/rspamd/local.d/dkim

# Create DKIM signing key map
cat << 'EOF' | sudo tee /etc/rspamd/local.d/dkim_signing.conf
# Domain → selector → key path
domain {
    ifinmail.local {
        path = "/etc/dkim/default.ifinmail.local.key";
        selector = "default";
    }
    eleso.local {
        path = "/etc/dkim/default.eleso.local.key";
        selector = "default";
    }
}

# Allow signing for these domains
allow_username_mismatch = true;
sign_local = true;
use_esld = false;
try_fallback = true;
EOF

# --- Step 2: SPF module ---
cat << 'EOF' | sudo tee /etc/rspamd/local.d/spf.conf
spf_cache_size = 2k;
spf_cache_expire = 1d;
EOF

# --- Step 3: DMARC module ---
cat << 'EOF' | sudo tee /etc/rspamd/local.d/dmarc.conf
reporting = true;
report_settings {
    # Where to send aggregate reports
    rua = "dmarc@ifinmail.local";
}
EOF

# --- Step 4: Actions / thresholds ---
cat << 'EOF' | sudo tee /etc/rspamd/local.d/actions.conf
# Increase default scores slightly (tune based on experience)
actions {
    greylist = 4.0;
    "add header" = 6.0;
    rewrite_subject = 8.0;
    reject = 15.0;
}
EOF
```

```bash
# --- Step 5: Postfix milter integration ---
# Add Rspamd milter to Postfix
sudo postconf -e "milter_default_action = accept"
sudo postconf -e "milter_protocol = 6"
sudo postconf -e "smtpd_milters = inet:localhost:11332"
sudo postconf -e "non_smtpd_milters = inet:localhost:11332"

# Enable milter for outbound mail too
sudo postconf -e "milter_mail_macros = i {mail_addr} {client_addr} {client_name} {auth_authen}"

# Configure Rspamd milter socket
cat << 'EOF' | sudo tee /etc/rspamd/local.d/worker-proxy.inc
milter = yes;
timeout = 120s;
upstream "local" {
    default = yes;
    self_scan = yes;
}
EOF

sudo systemctl reload postfix
sudo systemctl restart rspamd

# Verify milter connection
echo "Checking Rspamd milter socket..."
ls -la /var/run/rspamd/rspamd-milter.sock 2>/dev/null || ss -tlnp | grep 11332
```

```bash
# --- Test DKIM signing ---
# Send a test email and check for DKIM-Signature header
echo "Subject: DKIM Test
From: alice@ifinmail.local
To: bob@ifinmail.local

This message should be DKIM-signed." | sendmail -f alice@ifinmail.local bob@ifinmail.local

# Check the message headers for DKIM signature
sudo cat /var/mail/vhosts/ifinmail.local/bob/new/* 2>/dev/null | grep -i "dkim" | head -5
```

### Checkpoint Questions
1. What does the milter protocol allow Postfix to do during the SMTP transaction?
2. Why set different thresholds for greylist (4.0) vs reject (15.0)?
3. How does Rspamd's DKIM signing module know which key to use for which domain?
4. What happens if the milter socket is unreachable? (Hint: `milter_default_action = accept`)

### Connection to ifinmail App
Rspamd is now fully integrated: SPF checking, DKIM signing, DMARC evaluation, and spam filtering. Every inbound message passes through Rspamd before delivery. Every outbound message gets DKIM-signed. This is the proposal Section 5.3 brought to life.

---

## Day 5 (Friday): MTA-STS, TLS-RPT & DNS Health Dashboard

### Learning Objectives
- Understand MTA-STS and TLS-RPT for transport security
- Build the DNS health checking module for the admin dashboard
- Implement automated DNS record verification
- Create the deliverability status page foundations

### Theory / Reading
- **MTA-STS**: policy file at `https://mta-sts.<domain>/.well-known/mta-sts.txt` that tells senders "always use TLS"
- **TLS-RPT**: report of TLS failures sent to `smtp._tls.<domain>` TXT record
- **DNS health**: checking all records are present and correct (MX, SPF, DKIM, DMARC, MTA-STS, TLS-RPT, PTR)

### Practical Exercise
```bash
# MTA-STS policy file (served via HTTPS, not DNS!)
sudo mkdir -p /var/www/mta-sts/.well-known
cat << 'EOF' | sudo tee /var/www/mta-sts/.well-known/mta-sts.txt
version: STSv1
mode: testing
mx: mail.ifinmail.local
max_age: 86400
EOF

# MTA-STS DNS record
echo "DNS TXT Record:"
echo "  Name:   _mta-sts.ifinmail.local"
echo "  Value:  v=STSv1; id=20240512000001"

# TLS-RPT DNS record
echo ""
echo "DNS TXT Record:"
echo "  Name:   _smtp._tls.ifinmail.local"
echo "  Value:  v=TLSRPTv1; rua=mailto:tls-reports@ifinmail.local"
```

```python
# ~/ifinmail-python/dns_health_checker.py
"""
DNS Health Checker for ifinmail Admin Dashboard (Proposal Section 5.4 + 6.5)
"""
import subprocess
import json
from typing import Dict, List, Optional

def dig(domain: str, record_type: str) -> List[str]:
    """Run dig and return answer lines."""
    try:
        result = subprocess.run(
            ["dig", "+short", domain, record_type],
            capture_output=True, text=True, timeout=5
        )
        return [line for line in result.stdout.strip().split('\n') if line]
    except Exception:
        return []

def check_mx(domain: str) -> Dict:
    """Check MX records exist and return status."""
    records = dig(domain, "MX")
    return {
        "check": "mx",
        "status": "PASS" if records else "FAIL",
        "records": records,
        "message": "MX records found" if records else "No MX records — mail will not be delivered",
    }

def check_spf(domain: str) -> Dict:
    """Check SPF TXT record exists."""
    records = dig(domain, "TXT")
    spf = [r for r in records if "v=spf1" in r]
    return {
        "check": "spf",
        "status": "PASS" if spf else "FAIL",
        "records": spf,
        "message": "SPF record found" if spf else "No SPF record — outgoing mail may be rejected",
    }

def check_dkim(domain: str, selector: str = "default") -> Dict:
    """Check DKIM TXT record for a given selector."""
    dkim_domain = f"{selector}._domainkey.{domain}"
    records = dig(dkim_domain, "TXT")
    dkim = [r for r in records if "v=DKIM1" in r]
    return {
        "check": f"dkim ({selector})",
        "status": "PASS" if dkim else "FAIL",
        "records": dkim,
        "message": f"DKIM key found for selector '{selector}'" if dkim else f"No DKIM record for selector '{selector}'",
    }

def check_dmarc(domain: str) -> Dict:
    """Check DMARC TXT record."""
    dmarc_domain = f"_dmarc.{domain}"
    records = dig(dmarc_domain, "TXT")
    dmarc = [r for r in records if "v=DMARC1" in r]
    return {
        "check": "dmarc",
        "status": "PASS" if dmarc else "FAIL",
        "records": dmarc,
        "message": "DMARC policy found" if dmarc else "No DMARC policy — receivers may not act on SPF/DKIM failures",
    }

def check_ptr(ip_address: str) -> Dict:
    """Check reverse DNS (PTR) record."""
    records = dig(f"{'.'.join(reversed(ip_address.split('.')))}.in-addr.arpa", "PTR")
    return {
        "check": "ptr",
        "status": "PASS" if records else "FAIL",
        "records": records,
        "message": "PTR record found" if records else "No PTR record — some providers require this",
    }

def run_all_checks(domain: str, ip_address: Optional[str] = None) -> List[Dict]:
    """Run all DNS health checks for a domain."""
    checks = [
        check_mx(domain),
        check_spf(domain),
        check_dkim(domain),
        check_dmarc(domain),
    ]
    if ip_address:
        checks.append(check_ptr(ip_address))
    
    # Summary
    passed = sum(1 for c in checks if c["status"] == "PASS")
    total = len(checks)
    checks.append({
        "check": "summary",
        "status": "PASS" if passed == total else "WARN" if passed > 0 else "FAIL",
        "records": [],
        "message": f"{passed}/{total} checks passed",
    })
    
    return checks

if __name__ == "__main__":
    # Test with a known-good domain
    results = run_all_checks("gmail.com", "142.250.80.5")
    print(json.dumps(results, indent=2))
```

### Checkpoint Questions
1. What problem does MTA-STS solve that STARTTLS alone does not?
2. Why is MTA-STS served over HTTPS rather than just a DNS record?
3. How would the DNS health checker run continuously for all ifinmail domains?
4. What action should the admin dashboard take when DNS checks fail?

### Connection to ifinmail App
The DNS health checker is the core of the deliverability dashboard (proposal Section 6.5). In production, this runs as a background task checking every domain on the platform, flagging misconfigurations before they cause delivery failures.

---

## Day 6 (Saturday): Review & Integration

### Review Challenge: Complete Email Authentication Report

Write a script `~/ifinmail-scripts/auth_report.sh` that:

1. Takes a domain name as input
2. Checks SPF, DKIM, DMARC, MX, PTR, MTA-STS, TLS-RPT records
3. Parses each record and validates its syntax
4. Outputs a color-coded report (green PASS, yellow WARN, red FAIL)
5. Suggests fixes for any failing checks
6. Generates a JSON summary suitable for the API

**Stretch goal**: Use the actual Postfix queue and Rspamd stats to show real deliverability metrics alongside DNS health.

### Week 7 Self-Assessment

Before moving to Week 8, confirm you can:
- [ ] Write correct SPF, DKIM, and DMARC DNS records for a domain
- [ ] Generate DKIM keys and configure Rspamd DKIM signing
- [ ] Configure Rspamd milter integration with Postfix
- [ ] Explain DMARC alignment and reporting
- [ ] Set spam score thresholds and understand their trade-offs
- [ ] Write MTA-STS policies and TLS-RPT records
- [ ] Build a DNS health checker that validates all email authentication records

---

## Week 7 Resource Index

| Resource | Location |
|---|---|
| SPF syntax reference | `references/spf_guide.md` |
| DKIM key management | `references/dkim_guide.md` |
| DMARC policy guide | `references/dmarc_guide.md` |
| Rspamd module reference | `references/rspamd_modules.md` |
| Postfix milter integration | `references/postfix_milter.md` |
| MTA-STS implementation | `references/mta_sts.md` |
| DNS health checker code | `code/dns_health_checker.py` |

---

## Month 2 Completion Checklist

- [ ] **Postfix**: Virtual domains, PostgreSQL maps, TLS, submission service
- [ ] **Dovecot**: Maildir storage, SQL auth, LMTP integration, Sieve, doveadm
- [ ] **Email Security**: SPF, DKIM, DMARC, Rspamd, MTA-STS, DNS health
- [ ] **Integration**: Full inbound/outbound mail flow with authentication and filtering

You can now configure a complete, production-grade mail stack. Month 3 adds the API layer, Rust core, frontend, and deployment.

---

*Week 7 of 12 — Email Security & Authentication for ifinmail Platform Engineering*

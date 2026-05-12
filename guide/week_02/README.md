# Week 2: Networking & Email Protocols

**Month 1: Foundations | Days 7–12**

Email flows across the internet using protocols refined over 40+ years. This week covers TCP/IP fundamentals, DNS, and the three protocols at the heart of ifinmail: SMTP, IMAP, and TLS. No email system can be built without understanding what happens between `MAIL FROM` and `logout`.

---

## Learning Goals for the Week

By Sunday, you will be able to:

- Explain the TCP/IP and OSI models at a practical level
- Understand DNS: A, MX, CNAME, TXT, PTR records and how resolution works
- Read and write raw SMTP and IMAP sessions over telnet/openssl
- Explain how TLS encrypts mail in transit
- Map every protocol in the ifinmail stack to its port and purpose
- Troubleshoot basic connectivity issues with `dig`, `curl`, `nc`, and `openssl`

---

## Day 1 (Monday): TCP/IP Fundamentals

### Learning Objectives
- Understand the TCP/IP stack layers
- Know how TCP connections are established (SYN, SYN-ACK, ACK)
- Understand ports and how services bind to them
- Use `netstat`, `ss`, and `nc` to inspect network state

### Theory / Reading
- **TCP/IP layers**: Application → Transport (TCP/UDP) → Internet (IP) → Link
- **Ports**: 16-bit numbers identifying services on a host (SMTP=25, IMAP=143, HTTPS=443)
- **TCP handshake**: three-way handshake establishes reliable connections
- **Well-known ports**: 0–1023 require root to bind; we care about 25, 465, 587, 993, 995, 143, 110

### Practical Exercise
```bash
# See listening services
ss -tlnp | head -20        # TCP listening sockets
ss -ulnp | head -10         # UDP listening sockets

# Understand what's listening
ss -tlnp | grep -E ":(25|143|993|587) "  # Mail-related ports

# Create a simple TCP listener (one terminal)
nc -l 9090 &

# Connect to it (another terminal, or same)
echo "HELO ifinmail" | nc localhost 9090

# Kill the listener
kill %1

# Examine connections
netstat -natp 2>/dev/null | head -20 || ss -tanp | head -20
```

### Checkpoint Questions
1. What are the TCP ports for SMTP, SMTPS, Submission (587), IMAP, and IMAPS?
2. Why does email use TCP and not UDP?
3. What is the difference between a listening socket and an established connection?
4. If port 25 is already bound, what error will Postfix produce on startup?

### Connection to ifinmail
Postfix binds to ports 25 (SMTP), 465 (SMTPS), and 587 (submission). Dovecot binds to 143 (IMAP) and 993 (IMAPS). If these ports are occupied, mail stops. Understanding ports is the first step in debugging "mail isn't flowing."

---

## Day 2 (Tuesday): DNS Deep Dive

### Learning Objectives
- Understand DNS resolution (recursive vs authoritative)
- Know every record type relevant to email: A, MX, CNAME, TXT, PTR
- Use `dig` to query and troubleshoot DNS
- Understand how MX records control mail routing

### Theory / Reading
- **DNS hierarchy**: root servers → TLD servers → authoritative nameservers
- **MX records**: priority-based mail routing; lower values = higher priority
- **TXT records**: SPF, DKIM selectors, DMARC policies, domain verification
- **PTR records**: reverse DNS for IP reputation
- **TTL**: time-to-live controls caching behavior

### Practical Exercise
```bash
# Query MX records (where does mail go?)
dig gmail.com MX +short
dig outlook.com MX +short
dig ifinmail.com MX +short 2>/dev/null || echo "ifinmail.com does not exist yet"

# Query all record types for a domain
dig gmail.com ANY +short | head -20

# Trace DNS resolution from root
dig gmail.com MX +trace | head -30

# Query TXT records (SPF, DKIM, DMARC live here)
dig gmail.com TXT +short | head -10

# Reverse DNS (PTR)
dig -x 8.8.8.8 +short

# Check a domain's nameservers
dig gmail.com NS +short

# Simulate: what records does our ifinmail proposal require?
echo "Required DNS records for an ifinmail domain:"
echo "  MX: mail.ifinmail.com (priority 10)"
echo "  TXT (SPF): v=spf1 mx -all"
echo "  TXT (DKIM): default._domainkey IN TXT (v=DKIM1; k=rsa; p=...)"
echo "  TXT (DMARC): _dmarc IN TXT (v=DMARC1; p=quarantine; rua=mailto:...) "
echo "  A: mail.ifinmail.com → server IP"
echo "  PTR: server IP → mail.ifinmail.com"
```

### Checkpoint Questions
1. If a domain has two MX records with priorities 10 and 20, which server is tried first?
2. What happens if a domain has NO MX record?
3. Why is reverse DNS (PTR) important for email deliverability?
4. Where would you check if a domain's SPF record is correctly configured?

### Connection to ifinmail
Section 5.4 of the proposal dedicates an entire subsection to DNS identity records. The admin dashboard must "continuously check DNS health." Every domain hosted on ifinmail needs MX, SPF, DKIM, DMARC, MTA-STS, TLS-RPT, and PTR records correctly configured. You will implement these checks in Week 7.

---

## Day 3 (Wednesday): SMTP — The Sending Protocol

### Learning Objectives
- Understand the SMTP conversation flow (HELO, MAIL FROM, RCPT TO, DATA, QUIT)
- Read SMTP response codes (2xx success, 4xx temporary fail, 5xx permanent fail)
- Send a raw email using `nc` or `openssl s_client`
- Understand the difference between MUA, MSA, MTA, and MDA

### Theory / Reading
- **SMTP flow**: HELO/EHLO → MAIL FROM → RCPT TO → DATA → headers + body → `.` → QUIT
- **Roles**: MUA (mail user agent, e.g., Thunderbird), MSA (submission agent, port 587), MTA (mail transfer agent, Postfix), MDA (mail delivery agent, Dovecot LMTP)
- **Envelope vs headers**: `MAIL FROM` is the envelope sender (bounces go here); `From:` header is what the recipient sees

### Practical Exercise
```bash
# Raw SMTP session — connect to a mail server and say HELO
# (Use a test mail server; do NOT use this for spam)
echo "Attempting SMTP connection to gmail's MX..."
# We will just observe, not actually relay
printf "EHLO test.ifinmail.local\r\nQUIT\r\n" | nc -w 5 gmail-smtp-in.l.google.com 25 2>/dev/null || echo "Port 25 outbound may be blocked (common on residential connections)"

# Read SMTP response codes reference
cat << 'EOF'
Key SMTP Response Codes:
  220  Service ready
  250  Requested action OK
  354  Start mail input; end with <CRLF>.<CRLF>
  421  Service not available (connection will close)
  450  Mailbox unavailable (temporary)
  550  Mailbox unavailable (permanent)
  554  Transaction failed
EOF
```

### Checkpoint Questions
1. What is the difference between envelope `MAIL FROM` and the `From:` header?
2. Why would a server respond with `450` vs `550` for a mailbox?
3. What port should a user's email client use to *send* mail? Why not port 25?
4. In the ifinmail architecture, which component acts as MTA? Which acts as MDA?

### Connection to ifinmail
Postfix is ifinmail's MTA. Dovecot's LMTP is the MDA. Users submit mail on port 587 (submission) after authentication. Port 25 receives inbound mail from other servers. The API wraps these into clean endpoints — but underneath, SMTP is still doing the work.

---

## Day 4 (Thursday): IMAP — The Reading Protocol

### Learning Objectives
- Understand the IMAP conversation flow
- Differentiate IMAP from POP3
- Read an IMAP session using `openssl s_client`
- Understand mailbox hierarchy, flags, and IMAP commands

### Theory / Reading
- **IMAP**: messages stay on the server; clients sync state
- **POP3**: download-and-delete (mostly); simpler but less capable
- **IMAP commands**: LOGIN, SELECT, FETCH, STORE, SEARCH, LOGOUT
- **IMAP flags**: \Seen, \Answered, \Flagged, \Deleted, \Draft, \Recent
- **IMAPS**: IMAP over TLS on port 993

### Practical Exercise
```bash
# Observe IMAP over TLS (will fail gracefully if no account)
echo "IMAP uses persistent connections, unlike SMTP which is command-response."
echo "Commands include: LOGIN, SELECT INBOX, FETCH, SEARCH, LOGOUT"

# Reference: IMAP command set
cat << 'EOF'
Common IMAP Commands (used by Dovecot):
  a1 LOGIN username password
  a2 SELECT INBOX
  a3 FETCH 1:* FLAGS
  a4 FETCH 1 (BODY[HEADER])
  a5 FETCH 1 (BODY[TEXT])
  a6 STORE 1 +FLAGS (\Seen)
  a7 SEARCH UNSEEN
  a8 LOGOUT

IMAP Response Prefixes:
  *   Untagged response (data)
  a1  Tagged response (command complete)
  OK  Success
  NO  Failure
  BAD Protocol error
EOF
```

### Checkpoint Questions
1. Why does ifinmail use IMAP (via Dovecot) rather than POP3?
2. What is the difference between `\Deleted` and actually removing a message?
3. How does the ifinmail API relate to IMAP? Why have both?
4. What port does IMAP-over-TLS use?

### Connection to ifinmail
Dovecot provides IMAP for traditional clients (Thunderbird, Outlook, Apple Mail), while the ifinmail API provides the same data for official apps (Android, desktop, web). Both read from the same Maildir storage. This dual-access is a key architectural decision.

---

## Day 5 (Friday): TLS & Secure Communication

### Learning Objectives
- Understand TLS handshake and certificates
- Use `openssl s_client` to inspect certificates
- Know why STARTTLS exists and why it is insufficient
- Understand the difference between opportunistic and mandatory TLS

### Theory / Reading
- **TLS handshake**: ClientHello → ServerHello + Certificate → Key exchange → Encrypted channel
- **Certificates**: X.509, chain of trust, CA/B forum, Let's Encrypt
- **STARTTLS**: upgrade a plaintext connection to TLS on the same port
- **MTA-STS**: policy telling senders "always use TLS for this domain"
- **Certificate pinning**: client stores expected certificate/public key

### Practical Exercise
```bash
# Inspect a real mail server's certificate
echo "Q" | openssl s_client -connect gmail-smtp-in.l.google.com:25 -starttls smtp 2>/dev/null | openssl x509 -noout -subject -dates -issuer

echo ""
echo "=== Certificate details ==="
echo "Q" | openssl s_client -connect gmail-smtp-in.l.google.com:25 -starttls smtp 2>/dev/null | openssl x509 -noout -fingerprint -sha256

# Understand certificate chains
echo ""
echo "=== Full chain ==="
echo "Q" | openssl s_client -connect gmail-smtp-in.l.google.com:25 -starttls smtp -showcerts 2>/dev/null | grep -E "subject=|issuer=|BEGIN|END"

# Generate a self-signed certificate for practice (use for testing only!)
mkdir -p ~/ifinmail-certs
openssl req -x509 -newkey rsa:2048 -keyout ~/ifinmail-certs/test.key -out ~/ifinmail-certs/test.crt -days 7 -nodes -subj "/CN=test.ifinmail.local"
openssl x509 -in ~/ifinmail-certs/test.crt -noout -text | head -20
```

### Checkpoint Questions
1. Why is STARTTLS considered weaker than implicit TLS (ports 465/993)?
2. What does MTA-STS do that opportunistic TLS does not?
3. How does Certbot/ACME automate certificate renewal?
4. What is the relationship between TLS certificates and the `.ifinmail-*` security model?

### Connection to ifinmail
The proposal mandates "TLS everywhere" (Section 13.3). DANE/DNSSEC can complement MTA-STS. Certbot automates certificate lifecycle for Postfix and Dovecot. Certificate pinning is an option for official ifinmail apps.

---

## Day 6 (Saturday): Review & Integration

### Review Challenge: DNS Health Checker Script

Write a script `~/ifinmail-scripts/dns_health.sh` that takes a domain name and:

1. Checks if the domain resolves (A record exists)
2. Lists MX records with priorities
3. Checks for SPF TXT record (any record starting with `v=spf1`)
4. Checks for DMARC record (`_dmarc.<domain>` TXT)
5. Checks reverse DNS for the primary MX server's IP
6. Reports PASS/WARN/FAIL for each check
7. Outputs a summary suitable for the ifinmail admin dashboard

**Stretch goal**: Parse `dig +short` output cleanly and handle domains with no records gracefully.

### Week 2 Self-Assessment

Before moving to Week 3, confirm you can:
- [ ] Explain the TCP three-way handshake to a peer
- [ ] List all DNS record types needed for a working mail domain
- [ ] Write a raw SMTP HELO/EHLO conversation on a whiteboard
- [ ] Explain IMAP vs POP3 and why ifinmail uses IMAP
- [ ] Describe the TLS handshake at a high level
- [ ] Use `dig`, `nc`, `openssl s_client`, and `ss` fluently
- [ ] Map every ifinmail port (25, 465, 587, 143, 993) to its protocol and purpose

---

## Week 2 Resource Index

| Resource | Location |
|---|---|
| TCP/IP reference | `references/tcpip_ports.md` |
| DNS cheat sheet | `references/dns_records.md` |
| SMTP command reference | `references/smtp_commands.md` |
| IMAP command reference | `references/imap_commands.md` |
| TLS setup guide | `references/tls_mail.md` |
| Day 6 challenge script | `challenges/week_02_dns_health.md` |

---

*Week 2 of 12 — Networking & Email Protocols for ifinmail Platform Engineering*

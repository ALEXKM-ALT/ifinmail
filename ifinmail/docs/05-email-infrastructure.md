# Email Infrastructure — Edge Cases (59–72)

## EC-59: Postfix Open Relay via `mynetworks` Misconfiguration
**File:** `postfix/main.cf:12`
**Risk:** Critical — Spam relay
**Description:** `mynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128` is correctly restricted to localhost. However, if a Docker container on the same Docker network (`ifinmail-net`) connects to Postfix without authentication (e.g., a compromised container), Postfix will reject relay as expected. But if Docker's IP forwarding is misconfigured or the container uses the host network stack, `127.0.0.0/8` becomes the host, and any process on the host can relay mail without authentication.
**Trigger:** Compromised host process using the loopback interface.
**Fix:** Remove `mynetworks` CIDR ranges or restrict them further; require SASL auth for all relaying.

---

## EC-60: Milter Default Action is `accept` — Rspamd Failure Means No Spam Filtering
**File:** `postfix/main.cf:54`
**Risk:** High — Spam bypass during Rspamd outage
**Description:** `milter_default_action = accept` means if Rspamd is down or unreachable, Postfix accepts ALL mail without spam filtering. An attacker can trigger a DoS on Rspamd (e.g., by sending many messages), wait for the milter to fail, and then send spam that bypasses all checks.
**Trigger:** Rspamd container crash or restart.
**Fix:** Set `milter_default_action = tempfail` to defer mail when Rspamd is unavailable, or set up Rspamd with a high-availability configuration.

---

## EC-61: No Sender Policy Framework (SPF) Strictness on Inbound
**File:** `postfix/main.cf:41-49`
**Risk:** Medium — Inbound spoofing
**Description:** Postfix has `smtpd_recipient_restrictions` but no `reject_unauth_destination` for inbound mail that checks SPF via `policyd-spf` or `spf-engine`. The SPF record is published for outbound mail, but inbound SPF checking is not configured. This means anyone can spoof your domain to your own users.
**Trigger:** Sending spoofed email from `admin@yourdomain.com` to another mailbox on the same server.
**Fix:** Implement SPF checking via `policyd-spf` or Rspamd's SPF module (which is configured but not enforced at the MTA level).

---

## EC-62: Dovecot's `ssl = required` Prevents Non-TLS IMAP Connections
**File:** `dovecot/10-ssl.conf:2`
**Risk:** Low — Client compatibility
**Description:** Dovecot has `ssl = required`, meaning all IMAP connections must use TLS. This is correct for security. However, some legacy email clients and monitoring tools that don't support TLS will fail to connect, and the error messages may not be clear. This is a deliberate security choice but worth documenting as a potential integration issue.
**Trigger:** Legacy email client without TLS support.
**Fix:** Document the TLS requirement; provide a STARTTLS option on port 143 as an alternative.

---

## EC-63: Postfix Rate Limits Apply Per Client IP, Not Per Authenticated User
**File:** `postfix/main.cf:83-86`
**Risk:** Medium — Rate limit bypass
**Description:** `smtpd_client_connection_rate_limit = 30` limits connections per IP address. If a single authenticated user shares an IP with other users (NAT, corporate network), they collectively hit the limit. Conversely, an attacker can authenticate with stolen credentials from multiple IPs without triggering per-user rate limits.
**Trigger:** Multiple users behind the same NAT; attacker with a botnet.
**Fix:** Add per-user rate limits via policy service in addition to per-IP limits.

---

## EC-64: No DMARC Reporting (rua/ruf) Configured
**File:** `provision.sh:print_dns:328`
**Risk:** Low — Blind to spoofing
**Description:** The DMARC policy `v=DMARC1; p=none;` has no `rua=` (aggregate report URI) or `ruf=` (forensic report URI). Without reporting, domain owners have no visibility into who is sending email on their behalf or if their domain is being spoofed by phishers.
**Trigger:** Domain spoofed; DMARC reports would have alerted the owner.
**Fix:** Add `rua=mailto:postmaster@<domain>` to the DMARC record and configure a mailbox for receiving reports.

---

## EC-65: DKIM Key Rotation Has No Rollover Support
**Files:** `provision.sh:ensure_dkim`, `domains/models.py:DKIMKey`
**Risk:** Medium — Email rejection during key rotation
**Description:** The `DKIMKey` model supports multiple keys with `active=True`, and the `dkim_signing.conf` selects a single selector. However, there is no supported workflow for key rotation: generate new key → publish DNS → wait for propagation → switch selector → remove old key. The provisioning script always generates a single key with selector "default."
**Trigger:** Needing to rotate DKIM keys due to compromise or policy.
**Fix:** Implement a DKIM rotation management command that supports multi-selector rollover.

---

## EC-66: Postfix and Dovecot Use `PGSSLMODE=prefer` Instead of `require`
**Files:** `docker-compose.yml:91,136`
**Risk:** Low — Downgrade attack on DB connections
**Description:** Postfix and Dovecot database connections use `PGSSLMODE=prefer`, meaning they will attempt TLS but fall back to plaintext if the server doesn't support it. An attacker on the Docker network could perform a man-in-the-middle attack to downgrade the connection and intercept email authentication credentials.
**Trigger:** Attacker on the Docker network performs MITM.
**Fix:** Change `PGSSLMODE=require` for both Postfix and Dovecot, and ensure PostgreSQL is configured with TLS.

---

## EC-67: No SPF `-all` (Hard Fail) — Uses `~all` (Soft Fail)
**File:** `provision.sh:print_dns:327`
**Risk:** Medium — Spoofing allowed
**Description:** The SPF record generated by `provision.sh` uses `~all` (soft fail, meaning "probably not authorized but still accept"). For production mail servers, `-all` (hard fail, "reject unauthorized senders") provides stronger spoofing protection. The DNS auto-configuration in `_build_records` also uses `-all`, creating inconsistency.
**Trigger:** Manual vs auto DNS configuration produce different SPF policies.
**Fix:** Standardize on `-all` in both `provision.sh` and `_build_records`, with documentation about the upgrade path.

---

## EC-68: Postfix and Dovecot Certificates Not Re-read on Renewal
**Files:** `postfix/main.cf:65`, `dovecot/10-ssl.conf:4`
**Risk:** Medium — Service outage after cert renewal
**Description:** Postfix and Dovecot read TLS certificates at startup and do not automatically reload them when Let's Encrypt renews them. The certbot deploy-hook restarts nginx but not Postfix or Dovecot. After certificate renewal, Postfix and Dovecot are still serving the old (now expired) certificate to SMTP and IMAP clients.
**Trigger:** Let's Encrypt certificate renewal.
**Fix:** Add Postfix and Dovecot restart to the certbot deploy hook.

---

## EC-69: No Greylisting or Recipient Rate Limiting for Inbound Mail
**Files:** Rspamd has greylisting configured but not enforced
**Risk:** Medium — Backscatter / spam amplification
**Description:** While Rspamd has greylisting configured (`local.d/greylist.conf`), it is not explicitly enforced by Postfix. Without proper greylisting or recipient verification limits, the server is vulnerable to backscatter attacks: spammers send to non-existent addresses, and the server bounces them to innocent third parties.
**Trigger:** Dictionary attack against non-existent mailboxes.
**Fix:** Ensure Postfix rejects unknown recipients at RCPT time (it already queries PostgreSQL for virtual mailboxes). Verify that `reject_unknown_recipient_domain` and the PostgreSQL maps effectively block non-local recipients.

---

## EC-70: Mailbox Deletion Does Not Clean Up Maildir Storage
**File:** Not implemented
**Risk:** Medium — Disk space leak
**Description:** There is no mailbox deletion endpoint in the Django layer. When (if implemented) a mailbox is deleted from the database, the corresponding Maildir directory on disk (`/var/mail/vhosts/<domain>/<user>`) is not removed. Over time, deleted mailboxes accumulate on disk, consuming storage.
**Trigger:** Deleting a mailbox and not cleaning up its Maildir.
**Fix:** Add a post-delete signal or service method that removes the Maildir when a mailbox is deleted.

---

## EC-71: Postfix Queue Growth Not Actionable Beyond Monitoring
**File:** `monitor.py:check_postfix_queue`
**Risk:** Low — Operational awareness
**Description:** The monitor detects `QUEUE_CRITICAL` (>200 deferred emails) and sends an alert, but there is no automated action or troubleshooting guide. A large deferred queue has many possible causes (DNS resolution failure, remote server rejecting, rate limiting). The operator has no tooling to inspect queue contents from the Django dashboard.
**Trigger:** Postfix queue grows due to remote delivery failure.
**Fix:** Add a dashboard panel showing deferred queue details (destination domain, error code, count) by parsing `postqueue -p` output.

---

## EC-72: Dovecot Auth Rate Limits Not Configured
**File:** Not configured
**Risk:** Medium — IMAP brute-force
**Description:** While fail2ban has a Dovecot jail, the jail only bans repeated authentication failures after 5 attempts within 600 seconds. Between the first attempt and the ban, the attacker can make up to 5 attempts. Adding Dovecot-internal rate limiting (via `auth_worker_max_request_count` and `auth_failure_delay`) provides defense-in-depth.
**Trigger:** Brute-force attack against IMAP.
**Fix:** Configure `auth_failure_delay = 2 secs` and `auth_worker_max_request_count = 10` in Dovecot's `10-auth.conf`.

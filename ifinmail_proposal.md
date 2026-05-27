# ifinmail App Proposal

## Building a Secure, API-First Outlook/Gmail Competitor Using Postfix, Rust, Python, and Minimal Frontend Dependencies

## 1. Executive Summary

**ifinmail App** is proposed as a secure, API-first email platform designed to compete with Outlook, Gmail, and other hosted mail systems while giving users and businesses more control, transparency, portability, and trust.

The system will use proven mail infrastructure components such as **Postfix**, **Dovecot**, **Rspamd**, **OpenDKIM**, **OpenDMARC**, DNS-based authentication records, TLS, abuse controls, and reputation-management practices similar in spirit to Mail-in-a-Box. However, ifinmail App will not simply be a mail server bundle. It will be a full email platform with one stable API contract powering many official clients: Android, Windows, macOS, Linux, web, and future integrations.

The project will avoid unnecessary frontend and backend frameworks. The frontend will use server-rendered HTML, vanilla JavaScript, Web Components where useful, and strictly prefixed CSS classes such as `.ifinmail-*`. The backend will use Python and Rust where each is strongest: Python for orchestration, API development, admin workflows, and service glue; Rust for high-performance, security-sensitive, and reusable core components such as mail parsing, encryption, synchronization, policy enforcement, local client libraries, and device bootstrap agents.

The guiding principle is simple:

> **One mail platform. One API contract. Many clients. Minimal dependencies. Maximum control.**

---

## 2. Product Vision

ifinmail App should become a privacy-respecting, security-conscious, developer-friendly email service that users can trust for personal, business, and organizational communication.

Unlike typical webmail-only systems, ifinmail will be designed from the beginning as a multi-client ecosystem. Every client device, whether Android, Windows, macOS, Linux, browser, or future embedded device, will rely on the same backend API contract. This prevents fragmentation, inconsistent behavior, and duplicate business logic.

The platform should feel like a complete communication operating layer, not just a basic inbox. It should support secure mail hosting, reputation management, device onboarding, push notifications, account recovery, domain administration, mailbox migration, spam protection, audit logs, search, and future integrations with the wider ifinsta ecosystem.

---

## 3. Core Goals

### 3.1 Compete with Outlook and Gmail

ifinmail should provide the features users expect from mature email platforms:

- Custom domain email hosting.
- Personal and business mailboxes.
- Webmail.
- Android app.
- Windows and macOS desktop apps.
- IMAP/SMTP compatibility for third-party clients.
- Contact and calendar extensibility in later phases.
- Spam filtering and abuse prevention.
- Search, labels, folders, archive, drafts, sent mail, trash, and attachments.
- Admin dashboard for domains, users, aliases, routing, and security.

### 3.2 Use Postfix and proven mail tools

The platform should not reinvent core mail delivery. SMTP delivery is a mature, reputation-sensitive, standards-heavy area. ifinmail should use battle-tested tools:

- **Postfix** for SMTP sending and receiving.
- **Dovecot** for IMAP access, mailbox storage, authentication integration, and quota support.
- **Rspamd** for spam filtering, DKIM signing support, greylisting, fuzzy checks, reputation scoring, and policy decisions.
- **OpenDKIM / Rspamd DKIM module** for DKIM signing where appropriate.
- **OpenDMARC / Rspamd DMARC module** for DMARC policy evaluation and reporting.
- **PostgreSQL** for users, domains, aliases, device registrations, billing links, audit logs, and platform metadata.
- **Redis** for queues, rate limits, policy counters, and temporary verification flows.
- **Object storage** for large attachments and backup artifacts where needed.
- **Certbot or ACME-compatible tooling** for TLS certificate automation.

The goal is to build a modern product layer on top of reliable mail infrastructure, similar in discipline to Mail-in-a-Box, but more API-first, multi-client, and productized.

### 3.3 Minimize supply-chain attack risk

The system should avoid unnecessary dependencies, especially large JavaScript frontend frameworks and complex build pipelines.

Key rules:

- No React, Angular, Vue, or heavy frontend frameworks for the core product.
- No unnecessary npm dependency tree for production UI.
- Prefer plain HTML, CSS, vanilla JavaScript, and browser-native APIs.
- Use vendored, pinned, and audited assets.
- Avoid runtime CDN dependencies for production.
- Use Rust for security-sensitive reusable components.
- Use Python only with pinned dependencies and lockfiles.
- Generate SBOMs for backend, frontend, desktop, and mobile builds.
- Require signed commits, signed releases, reproducible builds where practical, and checksum verification.

---

## 4. Architecture Overview

ifinmail will consist of five major layers:

1. **Mail Infrastructure Layer**
2. **Core Platform API Layer**
3. **Shared Client Contract Layer**
4. **Client Applications Layer**
5. **Operations, Reputation, and Security Layer**

### 4.1 High-Level Architecture

```text
+--------------------------------------------------------------+
|                      Client Applications                     |
|  Android | Windows | macOS | Linux | Web | CLI | Integrations |
+----------------------------+---------------------------------+
                             |
                             | HTTPS / WebSocket / Device API
                             v
+--------------------------------------------------------------+
|                      ifinmail API Gateway                    |
|      Auth | Mail API | Device API | Admin API | Webhooks      |
+----------------------------+---------------------------------+
                             |
        +--------------------+--------------------+
        |                    |                    |
        v                    v                    v
+---------------+    +----------------+    +-------------------+
| Platform DB   |    | Mail Services  |    | Policy Services   |
| PostgreSQL    |    | Postfix/Dovecot|    | Rspamd/DMARC/etc. |
+---------------+    +----------------+    +-------------------+
        |                    |                    |
        v                    v                    v
+--------------------------------------------------------------+
|        Storage, Queues, Search, Logs, Backups, Monitoring     |
+--------------------------------------------------------------+
```

---

## 5. Mail Infrastructure Layer

### 5.1 Postfix

Postfix will be responsible for:

- Inbound SMTP receiving.
- Outbound SMTP sending.
- Queue management.
- Transport maps.
- Sender restrictions.
- Recipient restrictions.
- TLS enforcement where possible.
- Rate limits and policy delegation.
- Integration with Rspamd for filtering.
- Integration with Dovecot LMTP for mailbox delivery.

Postfix should remain close to upstream defaults where possible. Custom behavior should be implemented through policy services rather than fragile configuration hacks.

### 5.2 Dovecot

Dovecot will provide:

- IMAP access.
- LMTP delivery from Postfix.
- Mailbox storage using Maildir or an alternative carefully selected storage layout.
- Quotas.
- Authentication integration with ifinmail accounts.
- Sieve filtering support.
- Optional full-text search integration.

Dovecot gives compatibility with traditional mail clients while the ifinmail API powers official clients.

### 5.3 Rspamd

Rspamd will provide:

- Spam scoring.
- DKIM signing or verification.
- DMARC checks.
- SPF checks.
- Greylisting.
- Rate policy support.
- Reputation scoring.
- Fuzzy hashes.
- Malware scanning hooks.
- User-level spam learning.

Rspamd should be treated as a core component of deliverability and reputation management, not just a spam filter.

### 5.4 DNS and identity records

For every hosted domain, ifinmail must manage and verify:

- MX records.
- SPF records.
- DKIM records.
- DMARC records.
- MTA-STS records.
- TLS-RPT records.
- Reverse DNS alignment for sending IPs.
- HELO/EHLO identity.
- Bounce domain alignment.
- Tracking domain alignment where used.

The admin dashboard should continuously check DNS health and show clear warnings when a domain is misconfigured.

---

## 6. Reputation Management

Email reputation is one of the most important parts of this platform. A technically correct mail server is not enough. ifinmail must actively protect sender reputation, domain reputation, IP reputation, and platform reputation.

### 6.1 Reputation goals

- Prevent compromised accounts from sending spam.
- Prevent new users from immediately sending large volumes.
- Protect shared IP pools from abuse.
- Support dedicated IPs for serious business customers later.
- Track bounce rates, complaint rates, deferrals, blocklist status, and delivery failures.
- Provide transparent deliverability diagnostics.

### 6.2 Sending policy

Every sender should have policy limits based on trust level.

Example trust levels:

| Trust Level | Typical Account | Sending Limits |
|---|---|---|
| Level 0 | New unverified user | Very low daily/hourly limit |
| Level 1 | Verified user/domain | Moderate daily limit |
| Level 2 | Healthy sender history | Higher limits |
| Level 3 | Business verified | Business-grade limits |
| Level 4 | Dedicated reputation plan | Custom limits and dedicated IP option |

Signals used to determine trust:

- Domain age and verification status.
- SPF/DKIM/DMARC correctness.
- Bounce rate.
- Spam complaint rate.
- Sending velocity.
- Login risk.
- Account recovery events.
- Recipient engagement.
- Manual review status.

### 6.3 Warm-up strategy

New domains and new sending IPs must be warmed gradually. The platform should include:

- Daily sending caps.
- Gradual ramp-up schedule.
- Automatic throttling after bounces or complaints.
- Per-domain sending history.
- Per-IP reputation tracking.
- Provider-specific deferral handling.

### 6.4 Abuse controls

ifinmail should include:

- Outbound spam scanning.
- Suspicious link detection.
- Attachment scanning.
- Login anomaly detection.
- Impossible travel detection.
- Device trust checks.
- Rate limits per user, domain, IP, and organization.
- Temporary account lock on suspicious sending.
- Admin approval for high-volume sending.
- Manual review queues.

### 6.5 Deliverability dashboard

The admin dashboard should show:

- Domain DNS status.
- DKIM signing status.
- DMARC alignment status.
- SPF alignment status.
- Bounce trends.
- Deferral trends.
- Spam complaint trends.
- Blocklist monitoring results.
- Sending volume by user/domain.
- Top rejected recipients/domains.
- Reputation warnings and remediation steps.

---

## 7. API-First Platform Layer

ifinmail should expose one stable API contract that powers all official clients.

### 7.1 API principles

- Every core operation must be available through the API.
- API responses must be versioned.
- API errors must be structured and consistent.
- All write operations must support idempotency keys where useful.
- Clients must not depend on undocumented behavior.
- Backward compatibility should be preserved for supported client versions.
- API contracts should generate client bindings where practical.

### 7.2 Core API groups

#### Authentication API

- Login.
- Logout.
- Refresh token.
- Password reset.
- Multi-factor authentication.
- Device approval.
- Session listing.
- Session revocation.

#### Mail API

- List mailboxes.
- List messages.
- Read message.
- Send message.
- Save draft.
- Delete draft.
- Move message.
- Archive message.
- Mark read/unread.
- Star/unstar.
- Search mail.
- Download attachment.
- Upload attachment.

#### Admin API

- Create organization.
- Add domain.
- Verify domain DNS.
- Create mailbox.
- Create alias.
- Configure routing.
- Configure retention.
- View logs.
- View deliverability status.

#### Device Bootstrap API

- Register device.
- Issue device credential.
- Rotate device credential.
- Revoke device.
- Fetch client configuration.
- Fetch API contract version.
- Fetch feature flags.
- Fetch push notification settings.

#### WebSocket/Event API

- New message event.
- Message updated event.
- Mailbox updated event.
- Sending status event.
- Security alert event.
- Device revoked event.

---

## 8. Bootstrap Contracts for Client Devices

The bootstrap contract ensures that every official client can securely discover configuration, register itself, and communicate with the same API.

### 8.1 Why bootstrap contracts matter

Without a bootstrap contract, each app may implement account setup differently. That creates security gaps, inconsistent user experience, and difficult debugging.

The bootstrap contract standardizes:

- App identity.
- Device identity.
- API base URL discovery.
- Supported API versions.
- Feature flags.
- Device trust state.
- Encryption settings.
- Push notification configuration.
- Offline sync policy.
- Emergency revocation.

### 8.2 Bootstrap flow

```text
1. User installs client app.
2. Client calls /bootstrap/manifest.
3. Server returns API version, supported auth methods, public keys, and policy.
4. User signs in using password + MFA or device approval.
5. Client registers device using /devices/register.
6. Server returns device credential, sync settings, and feature flags.
7. Client uses the same Mail API contract as all other official clients.
```

### 8.3 Example bootstrap manifest

```json
{
  "service": "ifinmail",
  "api_version": "v1",
  "minimum_client_version": "1.0.0",
  "auth_methods": ["password", "mfa_totp", "passkey", "device_approval"],
  "endpoints": {
    "api": "https://api.ifinmail.com/v1",
    "websocket": "wss://api.ifinmail.com/v1/events",
    "status": "https://status.ifinmail.com"
  },
  "security": {
    "tls_required": true,
    "certificate_pinning": true,
    "device_key_required": true,
    "token_rotation_minutes": 30
  },
  "features": {
    "offline_mail": true,
    "encrypted_cache": true,
    "push_notifications": true,
    "local_search": true
  }
}
```

### 8.4 Client-specific bootstrap contracts

#### Android app

- Kotlin native client.
- Rust core accessed through JNI.
- Android Keystore for device private keys.
- Encrypted local mailbox cache.
- Push notifications through Firebase Cloud Messaging or a later self-hosted push strategy.
- Strict API contract generated from OpenAPI.

#### Windows app

- Rust-native desktop app or Tauri-style thin shell.
- Windows Credential Manager for secrets.
- Local encrypted SQLite cache.
- Background sync service.
- Signed installer.
- Auto-update with signature verification.

#### macOS app

- Swift or Rust-backed native app.
- Keychain for secrets.
- Local encrypted cache.
- Notification Center integration.
- Signed and notarized builds.
- Auto-update with signature verification.

#### Linux app

- Rust-native GUI or minimal webview shell.
- Secret Service API integration where available.
- AppImage, Flatpak, or distro package depending on phase.
- Signed packages.

#### Web client

- Server-rendered HTML where practical.
- Vanilla JavaScript modules.
- Web Components only where useful.
- Service Worker for offline read-only cache where safe.
- CSS classes prefixed with `.ifinmail-*`.
- No React or heavy frontend framework.

---

## 9. Minimal Frontend Strategy

### 9.1 Frontend rules

The frontend must be production-grade but dependency-light.

Rules:

- No React.
- No Angular.
- No Vue.
- No heavy SPA framework.
- No unnecessary npm-based build chain.
- No remote production CDN dependencies.
- CSS classes must be prefixed with `.ifinmail-*`.
- JavaScript modules should be small and audited.
- Use progressive enhancement: the page should still degrade safely.
- Prefer server-rendered pages for admin and mailbox views where possible.

### 9.2 CSS prefixing compliance

Every class used by ifinmail UI must use the `.ifinmail-*` prefix.

Examples:

```css
.ifinmail-shell {}
.ifinmail-sidebar {}
.ifinmail-message-list {}
.ifinmail-message-card {}
.ifinmail-compose-panel {}
.ifinmail-admin-warning {}
.ifinmail-domain-health {}
```

This prevents conflicts when ifinmail components are embedded into another dashboard, admin shell, or future ifinsta product surface.

### 9.3 Bootstrap usage

The phrase “bootstrap contracts” in this proposal refers mainly to **device bootstrap contracts**. However, if the project uses Bootstrap CSS for layout utilities, it should be handled carefully:

- Use a local vendored copy only.
- Remove unused components.
- Compile only required utilities.
- Prefix or scope Bootstrap styles under an `.ifinmail-*` shell where practical.
- Do not load Bootstrap JavaScript unless absolutely necessary.
- Avoid Popper or other JS dependencies unless justified.

The preferred approach is to build a small internal CSS utility layer instead of importing the full Bootstrap package.

---

## 10. Backend Technology Choices

### 10.1 Python

Python should be used for:

- API orchestration.
- Admin workflows.
- Billing integration.
- Internal tools.
- DNS verification workflows.
- Migration tools.
- Background tasks.
- Policy dashboards.

Recommended Python approach:

- Keep dependencies minimal.
- Use FastAPI only if the team accepts its dependency footprint.
- Otherwise use a smaller WSGI/ASGI stack.
- Use strict type hints.
- Use lockfiles.
- Run static analysis.
- Isolate services into small deployable units.

### 10.2 Rust

Rust should be used for:

- Mail parsing.
- MIME handling.
- Cryptographic routines.
- Local client cache engine.
- Sync engine.
- Policy engine.
- High-performance queue workers.
- Desktop application backend.
- Shared libraries for Android, desktop, and server.

Rust is especially suitable for code that must be reused across server and clients.

### 10.3 Integration layer

An integration layer will connect Python services, Rust libraries, Postfix, Dovecot, Rspamd, DNS systems, and client apps.

Possible approaches:

- Rust libraries exposed to Python through `pyo3`.
- Rust services communicating with Python over HTTP/gRPC.
- Command-based integration for mail server tooling where safer.
- PostgreSQL as shared system of record.
- Redis or NATS for event-driven communication.

The integration layer should be explicit and documented. Hidden coupling between services should be avoided.

---

## 11. Data Model

Core entities:

- Organization.
- Domain.
- User.
- Mailbox.
- Alias.
- Message metadata.
- Attachment metadata.
- Device.
- Session.
- API key.
- Sending identity.
- Reputation profile.
- DNS verification record.
- Audit event.
- Security event.
- Abuse review case.

Mail content itself may remain in Dovecot-compatible storage while metadata is indexed into PostgreSQL and search services.

---

## 12. Search and Indexing

Search should support:

- Sender.
- Recipient.
- Subject.
- Date range.
- Folder.
- Attachment presence.
- Read/unread.
- Full-text body search.

Initial implementation may use PostgreSQL full-text search for simplicity. Later, if scale requires, introduce a dedicated search engine. Any search engine must be evaluated carefully because search systems add operational and supply-chain complexity.

---

## 13. Security Model

### 13.1 Account security

- Password hashing using Argon2id.
- MFA support.
- Passkey support in later phase.
- Device approval.
- Session management.
- Login alerts.
- Recovery codes.
- Admin-enforced security policies.

### 13.2 Device security

- Device-specific credentials.
- Device revocation.
- Token rotation.
- Local encrypted cache.
- Platform key store integration.
- Remote wipe instruction for official clients where supported.

### 13.3 Transport security

- TLS everywhere.
- MTA-STS support.
- TLS reporting support.
- Certificate automation.
- Optional certificate pinning for official apps.

### 13.4 Mail security

- SPF verification.
- DKIM signing and verification.
- DMARC enforcement.
- Spam scanning.
- Malware scanning hooks.
- Suspicious attachment warnings.
- URL safety checks.
- Optional end-to-end encryption.

### 13.5 Supply-chain security

- Minimal dependencies.
- Lockfiles.
- SBOM generation.
- Signed releases.
- Reproducible build goals.
- Dependency review before upgrades.
- No unpinned CI/CD actions.
- No production dependency on public CDNs.
- Separate build environments from production secrets.

---

## 14. Operations and Deployment

### 14.1 Deployment model

Phase one can use a single well-hardened VPS or dedicated server for early testing, similar to Mail-in-a-Box simplicity. Production should support separation of concerns:

- Mail ingress nodes.
- Mail egress nodes.
- API nodes.
- Database nodes.
- Worker nodes.
- Monitoring node.
- Backup storage.

### 14.2 Backups

Backups must include:

- PostgreSQL.
- Mail storage.
- DKIM keys.
- Configuration snapshots.
- Audit logs where required.
- User recovery metadata.

Backup requirements:

- Encrypted at rest.
- Regular restore testing.
- Separate backup credentials.
- Immutable backup option for business plans.

### 14.3 Monitoring

Monitor:

- SMTP queue length.
- Delivery failures.
- Bounce rates.
- Rspamd scores.
- CPU and memory.
- Disk usage.
- IMAP login failures.
- API latency.
- API error rates.
- DNS misconfiguration.
- Certificate expiry.
- Blocklist status.

---

## 15. Development Phases

### Phase 1: Foundation

- Set up Postfix, Dovecot, Rspamd, PostgreSQL, Redis.
- Implement domain and mailbox management.
- Implement DNS verification.
- Implement sending and receiving.
- Implement DKIM, SPF, DMARC checks.
- Build basic admin CLI.
- Build simple webmail interface with server-rendered HTML.

### Phase 2: API Contract and Web Client

- Define OpenAPI contract.
- Implement Mail API.
- Implement Auth API.
- Implement Admin API.
- Implement Device Bootstrap API.
- Build framework-free web client.
- Enforce `.ifinmail-*` CSS prefixing.

### Phase 3: Reputation and Abuse Controls

- Add sending limits.
- Add trust levels.
- Add bounce processing.
- Add complaint handling.
- Add blocklist monitoring.
- Add deliverability dashboard.
- Add suspicious sending detection.

### Phase 4: Android Client

- Build native Android client.
- Implement bootstrap registration.
- Add encrypted local cache.
- Add push notifications.
- Use generated API contract.
- Integrate Rust core for parsing and sync.

### Phase 5: Desktop Clients

- Build Windows client.
- Build macOS client.
- Add signed installers.
- Add auto-update with signature verification.
- Add local encrypted cache.
- Reuse Rust core.

### Phase 6: Scale and Business Features

- Organization policies.
- Team administration.
- Shared mailboxes.
- Audit exports.
- Dedicated IP support.
- Advanced migration tools.
- Calendar and contacts expansion.
- ifinsta ecosystem integration.

---

## 16. Key Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Poor IP/domain reputation | Mail goes to spam | Warm-up, throttling, abuse controls, DNS health checks |
| Account compromise | Spam and data loss | MFA, device trust, anomaly detection, rate limits |
| Supply-chain attack | Code compromise | Minimal dependencies, SBOMs, signed releases, pinned builds |
| Mail server misconfiguration | Delivery failure | Automated diagnostics and configuration tests |
| Client fragmentation | Inconsistent behavior | One API contract and bootstrap standard |
| Storage growth | High costs and outages | Quotas, lifecycle policies, attachment limits |
| Spam abuse | Platform reputation damage | Rspamd, outbound scanning, trust levels, review queue |
| Complex operations | Team overload | Start simple, automate checks, document runbooks |

---

## 17. Definition of Success

ifinmail succeeds when:

- A user can create a mailbox and send/receive mail reliably.
- A domain admin can connect a custom domain and see DNS health clearly.
- Messages pass SPF, DKIM, and DMARC alignment.
- The system prevents new users from abusing outbound mail.
- Official clients share the same API behavior.
- Android, desktop, and web clients can bootstrap securely.
- The frontend remains lightweight and framework-free.
- Dependencies are known, pinned, audited, and minimized.
- The product feels refined enough to compete with established mail clients.

---

## 18. Final Recommendation

ifinmail should be built as a serious mail platform, not a simple webmail wrapper. The correct foundation is a blend of proven mail infrastructure and a modern API-first product layer.

The recommended stack is:

- **Postfix** for SMTP.
- **Dovecot** for IMAP and mailbox delivery.
- **Rspamd** for spam filtering, policy scoring, DKIM/DMARC support, and reputation controls.
- **PostgreSQL** for platform data.
- **Redis** for queues, counters, and temporary state.
- **Python** for orchestration, APIs, admin logic, and integration services.
- **Rust** for shared secure core components, parsing, sync, policy engines, and client libraries.
- **Framework-free frontend** using prefixed `.ifinmail-*` CSS, vanilla JavaScript, and server-rendered HTML.

This approach gives ifinmail the best balance between security, maintainability, performance, deliverability, and cross-platform consistency.

The result should be an email platform that can begin small, like a disciplined Mail-in-a-Box-inspired deployment, but grow into a robust Outlook/Gmail competitor with official apps, strong reputation controls, and one contract-driven ecosystem.


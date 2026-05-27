# ifinmail App

**A secure, API-first email platform. One contract. Many clients. Minimal dependencies.**

ifinmail App is an open-source email platform designed to compete with Outlook and Gmail while giving users and businesses more control, transparency, and trust. It combines battle-tested mail infrastructure (Postfix, Dovecot, Rspamd) with a modern API-first product layer (Python, Rust) and framework-free clients (Android, Windows, macOS, Linux, web).

---

## Architecture

```
+--------------------------------------------------------------+
|                     Client Applications                      |
|  Android | Windows | macOS | Linux | Web | CLI | Integrations |
+----------------------------+---------------------------------+
                             |
                             | HTTPS / WebSocket / Device API
                             v
+--------------------------------------------------------------+
|                     ifinmail API Gateway                     |
|     Auth | Mail API | Device API | Admin API | Webhooks      |
+----------------------------+---------------------------------+
                             |
        +--------------------+--------------------+
        |                    |                    |
        v                    v                    v
+---------------+    +----------------+    +-------------------+
| Platform DB   |    | Mail Services  |    | Policy Services   |
| PostgreSQL    |    | Postfix/Dovecot|    | Rspamd/DMARC      |
+---------------+    +----------------+    +-------------------+
```

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| SMTP | Postfix | Inbound/outbound mail delivery, queue management |
| IMAP / MDA | Dovecot | Mailbox storage (Maildir), IMAP access, LMTP delivery |
| Filtering | Rspamd | Spam, DKIM, DMARC, SPF, greylisting, reputation |
| Database | PostgreSQL | Users, domains, mail metadata, audit logs |
| Cache / Queues | Redis | Rate limits, counters, sessions, task queues |
| API Backend | Python (FastAPI) | REST API, admin workflows, orchestration |
| Core Libraries | Rust | Mail parsing, crypto, sync engine, policy engine |
| Frontend | Vanilla HTML/CSS/JS | Webmail, admin dashboard — no React/Angular/Vue |
| Infra | Docker, systemd, Certbot | Deployment, TLS, service management |

## Guiding Principles

- **One mail platform. One API contract. Many clients.** Every official client (Android, Windows, macOS, Linux, web) relies on the same backend API. No fragmentation.
- **Minimal dependencies.** No React, Angular, Vue, or heavy JavaScript build pipelines. Vanilla HTML, CSS, and JS with `.ifinmail-*` CSS prefixing. Pinned and audited dependencies with SBOMs.
- **Proven mail infrastructure.** Postfix, Dovecot, and Rspamd are battle-tested. ifinmail builds a modern product layer on top, not a replacement.
- **Security by design.** Argon2id password hashing, TLS everywhere, SPF/DKIM/DMARC, device-specific credentials, supply-chain security with signed commits and releases.

## Repository Structure

```
ifinmail/
  README.md                   — You are here
  ifinmail_proposal.md        — Full product proposal (architecture, phases, risks)
  guide/                      — 12-week engineering curriculum for new attaches
    README.md                 — Curriculum overview
    week_01/                  — Linux/Unix Fundamentals
    week_02/                  — Networking & Email Protocols
    week_03/                  — Python, Git & Development Environment
    week_04/                  — Databases & Data Modeling
    week_05/                  — Postfix & SMTP Configuration
    week_06/                  — Dovecot & IMAP
    week_07/                  — Email Security (SPF, DKIM, DMARC, Rspamd)
    week_08/                  — Python API Development
    week_09/                  — Rust Fundamentals
    week_10/                  — Minimal Frontend (HTML/CSS/JS)
    week_11/                  — Security, DevOps & Deployment
    week_12/                  — Capstone Project
```

## Quick Start

> The project is in early development. The guide above is the starting point for new engineers joining the team.

### For New Team Members

Start with the [curriculum guide](guide/README.md). It is a 12-week, self-paced program that takes you from Linux fundamentals to building a working mini-ifinmail App prototype. No prior email systems knowledge is required.

### For Everyone Else

Read the [full proposal](ifinmail_proposal.md) to understand the product vision, architecture, and development phases.

## Development Status

- **Current version**: v0.0.1 (proposal and curriculum only)
- **Phase**: Pre-implementation — building the engineering team

### Development Phases (from proposal)

| Phase | Scope |
|---|---|
| 1 — Foundation | Postfix, Dovecot, Rspamd, PostgreSQL, basic admin CLI, simple webmail |
| 2 — API Contract & Web Client | OpenAPI contract, Mail/Auth/Admin/Bootstrap APIs, framework-free web client |
| 3 — Reputation & Abuse | Trust levels, sending limits, bounce/complaint handling, deliverability dashboard |
| 4 — Android Client | Native Kotlin client, Rust core via JNI, encrypted cache, push notifications |
| 5 — Desktop Clients | Windows, macOS, Linux clients, signed installers, auto-update |
| 6 — Scale & Business | Organization policies, shared mailboxes, dedicated IPs, calendar/contacts |

## Key Documents

- [Full Product Proposal](ifinmail_proposal.md) — architecture, security model, reputation strategy, API design, risk analysis
- [Engineering Curriculum](guide/README.md) — 12-week training program for new attaches at Eleso Solution

## License

Proprietary — Eleso Solution / ifinsta flagship project.

---

*Built by Eleso Solution. Part of the ifinsta product ecosystem.*

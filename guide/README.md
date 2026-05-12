# ifinmail Engineering Curriculum

## 3-Month Training Program for New Attachees at Eleso Solution

This curriculum transforms new engineering attaches from foundational knowledge to delivering a working prototype of the **ifinmail** email platform — a secure, API-first Outlook/Gmail competitor built on Postfix, Rust, Python, and minimal frontend dependencies.

---

## Curriculum Philosophy

- **Incremental difficulty** — each week builds on the previous, never leaving anyone behind
- **Project-driven** — every concept is tied directly to the ifinmail proposal
- **Hands-on** — daily practical exercises, not just theory
- **Production-minded** — we teach security, reputation, and operations from day one

---

## Month 1: Foundations (Weeks 1–4)

Build the bedrock: operating systems, networking, programming, and data stores.

| Week | Topic | Key Technologies |
|---|---|---|
| [Week 1](week_01/) | Linux/Unix Fundamentals | Bash, file systems, permissions, processes, shell scripting, text processing |
| [Week 2](week_02/) | Networking & Email Protocols | TCP/IP, DNS, HTTP/HTTPS, SMTP, IMAP, POP3, TLS, ports |
| [Week 3](week_03/) | Python, Git & Development Environment | Python syntax, venv, pip, type hints, Git workflow, VS Code / terminal setup |
| [Week 4](week_04/) | Databases & Data Modeling | PostgreSQL, SQL, Redis, schema design, the ifinmail data model |

---

## Month 2: Core Mail Stack (Weeks 5–8)

Learn the mail infrastructure layer and begin building the API platform.

| Week | Topic | Key Technologies |
|---|---|---|
| [Week 5](week_05/) | Postfix & SMTP | Postfix configuration, virtual domains, TLS, queue management, transport maps |
| [Week 6](week_06/) | Dovecot & IMAP | Dovecot setup, Maildir storage, LMTP delivery, authentication, Sieve filtering |
| [Week 7](week_07/) | Email Security & Authentication | SPF, DKIM, DMARC, Rspamd, DNS records, reputation fundamentals |
| [Week 8](week_08/) | Python API Development | FastAPI, REST design, OpenAPI contracts, JWT auth, the ifinmail API groups |

---

## Month 3: Integration & Capstone (Weeks 9–12)

Bring everything together: Rust core, frontend, security, deployment, and the final project.

| Week | Topic | Key Technologies |
|---|---|---|
| [Week 9](week_09/) | Rust Fundamentals | Ownership, Cargo, crates, error handling, FFI with Python via pyo3 |
| [Week 10](week_10/) | Minimal Frontend | Server-rendered HTML, vanilla JS, `.ifinmail-*` CSS, Web Components |
| [Week 11](week_11/) | Security, DevOps & Deployment | TLS, Certbot, Docker, backups, monitoring, CI/CD, SBOMs |
| [Week 12](week_12/) | Capstone Project | Build a mini-ifinmail: send/receive mail, webmail UI, admin dashboard, API |

---

## Daily Schedule Format

Each week is broken into 5 training days (Monday–Friday). Each day includes:

1. **Learning Objectives** — what you will know by end of day
2. **Theory / Reading** — concepts and reference material
3. **Practical Exercise** — hands-on task
4. **Checkpoint Questions** — self-assessment
5. **Connection to ifinmail** — how this applies to the project

A sixth "Review & Practice" day (Saturday) provides consolidation exercises.

---

## Capstone Project: Mini-ifinmail

In Week 12, attaches will integrate everything into a working prototype:

- Configure Postfix + Dovecot for a test domain
- Build a Python FastAPI backend exposing Mail and Auth APIs
- Create a framework-free webmail UI with `.ifinmail-*` CSS
- Implement SPF, DKIM, DMARC for the test domain
- Deploy behind TLS with basic monitoring
- Present a working demo: send mail, receive mail, read inbox in browser

---

## Prerequisites

- A computer capable of running Linux (native, VM, or WSL2)
- Willingness to use the terminal as primary interface
- No prior email systems knowledge required — we start from zero

---

## Reference: The ifinmail Proposal

The full [ifinmail proposal](../ifinmail_proposal.md) is the north star for this curriculum. Attaches should re-read relevant sections each week as their understanding deepens.

---

## Tracking Progress

Each week's directory contains a `README.md` with daily materials and exercises. Attaches should:

1. Read the day's theory before the session
2. Complete the practical exercise during the session
3. Answer checkpoint questions honestly
4. Flag anything unclear to the instructor immediately

---

*Curriculum prepared for Eleso Solution — ifinsta flagship project*

# ifinmail — Unhandled Edge Cases Catalogue

> **Goal:** Document 100+ unhandled edge cases across all system layers to guide hardening efforts.
> **Status:** Living document — update as edge cases are fixed or new ones discovered.

---

## Documents

| # | File | Domain | Edge Cases |
|---|------|--------|------------|
| 1 | [01-auth-session.md](./01-auth-session.md) | Authentication & Session Security | EC-01–EC-15 |
| 2 | [02-database-data.md](./02-database-data.md) | Database & Data Integrity | EC-16–EC-30 |
| 3 | [03-api-web-security.md](./03-api-web-security.md) | API & Web Security | EC-31–EC-45 |
| 4 | [04-dns-provider.md](./04-dns-provider.md) | DNS Provider Integration | EC-46–EC-58 |
| 5 | [05-email-infrastructure.md](./05-email-infrastructure.md) | Email Infrastructure | EC-59–EC-72 |
| 6 | [06-file-storage.md](./06-file-storage.md) | File Upload & Storage | EC-73–EC-81 |
| 7 | [07-monitoring-observability.md](./07-monitoring-observability.md) | Monitoring & Observability | EC-82–EC-91 |
| 8 | [08-backup-disaster-recovery.md](./08-backup-disaster-recovery.md) | Backup & Disaster Recovery | EC-92–EC-100 |
| 9 | [09-deployment-infrastructure.md](./09-deployment-infrastructure.md) | Deployment & Infrastructure | EC-101–EC-110 |

---

**Total: 110 edge cases identified across 9 domains.**

## Severity Distribution

| Severity | Count | Examples |
|----------|-------|----------|
| **Critical** | 3 | EC-02 (empty password superuser), EC-59 (open relay on milter failure), EC-92 (GPG key not backed up = permanent data loss) |
| **High** | 15 | EC-01, EC-11, EC-14, EC-16, EC-18, EC-36, EC-46, EC-48, EC-50, EC-54, EC-60, EC-73, EC-75, EC-78, EC-102 |
| **Medium** | 40 | EC-03–EC-05, EC-07, EC-08, EC-12, EC-17, EC-20, EC-21, EC-23, EC-26, EC-28, EC-29, EC-31, EC-35, EC-39, EC-43, EC-49, EC-51, EC-52, EC-55, EC-56, EC-63, EC-65, EC-67, EC-68, EC-69, EC-70, EC-74, EC-76, EC-77, EC-81, EC-84, EC-85, EC-91, EC-93, EC-94, EC-97, EC-99, EC-103, EC-105, EC-107, EC-110 |
| **Low** | 19 | EC-06, EC-19, EC-22, EC-24, EC-25, EC-27, EC-32, EC-33, EC-34, EC-40, EC-41, EC-44, EC-45, EC-53, EC-57, EC-62, EC-66, EC-71, EC-79 |

## Common Attack Patterns

| Pattern | Edge Cases |
|---------|------------|
| **Authentication Bypass** | EC-02, EC-08, EC-11 |
| **Credential Exposure** | EC-12, EC-36, EC-37 |
| **DNS Manipulation** | EC-46, EC-50, EC-54, EC-55 |
| **Data Loss** | EC-14, EC-92, EC-96, EC-97 |
| **Privilege Escalation** | EC-08, EC-15 |
| **Resource Exhaustion** | EC-23, EC-31, EC-70, EC-74, EC-79 |
| **Spoofing / Phishing** | EC-05, EC-61, EC-64, EC-67 |
| **Session Hijacking** | EC-01, EC-07 |
| **Brute-Force Bypass** | EC-03, EC-72 |

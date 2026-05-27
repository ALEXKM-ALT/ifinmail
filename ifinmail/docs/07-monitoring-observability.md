# Monitoring & Observability — Edge Cases (82–91)

## EC-82: Monitor Cache Poisoning via Untrusted Redis Data
**File:** `services/monitoring.py:24-30`
**Risk:** Low — Display manipulation
**Description:** `get_latest_report()` loads JSON from Redis and deserializes it with `json.loads()`. There is no schema validation on the loaded data. If Redis is compromised or if the wrong Redis key is overwritten by a different process, the monitoring dashboard will display arbitrary data.
**Trigger:** Redis key `ifinmail:monitor:latest` overwritten by another process.
**Fix:** Validate the loaded data structure against a schema (e.g., `{"timestamp": str, "services": dict, "overall": str}`) before processing.

---

## EC-83: Monitor Lock File Race Condition on Concurrent Execution
**File:** `monitor.py:387-397`
**Risk:** Low — Duplicate execution
**Description:** The lock file mechanism uses `fcntl.flock()` with `LOCK_EX | LOCK_NB`. This works for processes on the same machine. However, if the monitor runs inside a Docker container and the lock file is on an overlay filesystem, the lock may not be visible to other instances. With horizontal scaling of the API container (multiple replicas), monitoring checks run multiple times concurrently.
**Trigger:** Multiple API container replicas running the monitor script.
**Fix:** Use a Redis-based distributed lock instead of a filesystem lock for containerized deployments.

---

## EC-84: DNS Health Check Uses `dig` with Default Resolver
**File:** `services/monitoring.py:93-141`
**Risk:** Medium — Inaccurate DNS status
**Description:** `MonitoringService.check_dns()` calls `dig +short MX <domain>` without specifying a DNS resolver (`@resolver`). This uses the container's default resolver (usually Docker's built-in DNS at `127.0.0.11` or the host's `/etc/resolv.conf`). If the container's DNS is misconfigured or the resolver caches stale data, DNS checks will report inaccurate results.
**Trigger:** Container DNS resolver misconfiguration or caching.
**Fix:** Use explicit public resolvers (`@8.8.8.8` or `@1.1.1.1`) for monitoring DNS checks, matching the approach in `DeliverabilityService._check_dns_propagation()`.

---

## EC-85: Monitor Delivery Rate Parsing Depends on Postfix Log Format
**File:** `monitor.py:142-168`
**Risk:** Medium — Broken metric
**Description:** `check_delivery_rate()` parses Postfix mail logs via `status=(sent|deferred|bounced)`. If the Postfix log format changes (upstream change, different log level, container restart with log rotation), the log parsing silently breaks and returns `{"error": ...}`. There's no validation that the parsed data is reasonable.
**Trigger:** Postfix log format change; log rotation between awk and grep calls.
**Fix:** Add sanity checks on parsed values (e.g., cannot have negative counts, totals should be > 0 on an active server).

---

## EC-86: Monitor Uses `psutil` as Optional Import — Degraded Fallback
**File:** `monitor.py:226-259`
**Risk:** Low — Incomplete metrics
**Description:** `check_system_resources()` tries to import `psutil` and falls back to reading `/proc` filesystem. On Alpine-based containers (which many ifinmail services use), `psutil` may be unavailable and `/proc/meminfo` has a different format than what's expected, causing parsing errors. The fallback returns `{"error": str(e)}` which is silently ignored in `run_all_checks()`.
**Trigger:** Monitor container without `psutil` on Alpine Linux.
**Fix:** Ensure `psutil` is installed in the monitor's runtime, or use a more robust `/proc` parser.

---

## EC-88: Alert State File May Become Corrupt
**File:** `monitor.py:286-334`
**Risk:** Low — Alert silence
**Description:** The alert state file is written with an atomic replace (`os.replace`), but the read is non-atomic. If the file is partially written when the reader runs (another monitor instance or read during write), the state is read as garbage, potentially preventing alert delivery.
**Trigger:** Monitor reads alert state file during concurrent write.
**Fix:** Read the file with retries or use a Redis key for alert state instead of a file.

---

## EC-89: Monitor History in Redis Grows Without Bound
**File:** `monitor.py:376`
**Risk:** Low — Redis memory
**Description:** `redis_client.ltrim("ifinmail:monitor:history", 0, 287)` limits history to 288 entries (one every 5 minutes = 24 hours). This works as intended, but if the monitor script fails to call `ltrim` (crashes between `lpush` and `ltrim`), the history list grows unbounded. Redis has no built-in limit on list size.
**Trigger:** Monitor crash between `lpush` and `ltrim`.
**Fix:** Run `ltrim` unconditionally before `lpush`, or set a Redis key-level `maxmemory-policy`.

---

## EC-90: No Monitoring of Celery Worker Health
**File:** Not implemented
**Risk:** Medium — Async task failures are invisible
**Description:** The system uses Celery (configured in settings), but there is no Celery worker container in Docker Compose and no health check for Celery task queues. If async tasks (future: file processing, email sending) are configured without worker monitoring, task failures will go undetected.
**Trigger:** Celery worker crash; queued tasks never execute.
**Fix:** Add a Celery worker container to Docker Compose with a dedicated health check (celery inspect).

---

## EC-91: Rspamd Controller Password Not Set by Default
**File:** `docker-compose.yml:174`
**Risk:** Medium — Unauthenticated Rspamd web UI
**Description:** `RSPAMD_CONTROLLER_PASSWORD` is loaded from `.env` but is empty if not explicitly set. The Rspamd controller web UI (port 11334) is bound to localhost, which limits exposure, but if an attacker gains access to the host machine, they can access the full Rspamd UI without authentication, modify spam rules, and view email scores (leaking content information).
**Trigger:** `RSPAMD_CONTROLLER_PASSWORD` not set; attacker has host access.
**Fix:** Make `RSPAMD_CONTROLLER_PASSWORD` required (fail to start if empty) and add a default generation in `provision.sh`.

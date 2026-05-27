# Database & Data Integrity — Edge Cases (16–30)

## EC-16: Unmanaged Models Risk Schema Drift Between Django and init-db.sh
**Files:** `models/*.py` (all models with `managed = False`), `init-db.sh`
**Risk:** High — Silent data corruption
**Description:** Five models (`MailUser`, `Domain`, `Mailbox`, `Alias`, `DKIMKey`) are `managed = False`, meaning Django never validates or migrates their schema. The schema is defined solely in `init-db.sh`. Any change to one without the corresponding change to the other causes runtime failures. There is no CI check that enforces schema parity.
**Trigger:** Adding a field to a Django model without updating `init-db.sh`, or vice versa.
**Fix:** Add a CI check that compares Django's `sqlmigrate` output against `init-db.sh` table definitions.

---

## EC-17: Missing Unique Constraints on Alias Destination
**File:** `init-db.sh:55-60`
**Risk:** Medium — Mail routing ambiguity
**Status:** ✅ Fixed — Added `UNIQUE(domain_id, source, destination)` constraint
**Description:** The `aliases` table has no unique constraint on `(domain_id, source, destination)`. An alias like `info@ → admin@` can be duplicated, causing Postfix to deliver duplicate emails or pick a non-deterministic row.
**Trigger:** Creating duplicate alias records via the API/admin.
**Fix:** Add `UNIQUE(domain_id, source, destination)` constraint.

---

## EC-18: No ON DELETE CASCADE or Atomicity for Domain Deletion
**File:** `init-db.sh:48,56,63`
**Risk:** High — Orphaned records
**Status:** ✅ Fixed — Added `DomainService.delete_domain()` with `transaction.atomic()`
**Description:** `mailboxes`, `aliases`, and `dkim_keys` have `REFERENCES domains(id) ON DELETE CASCADE`, so deleting a domain cascades. However, there is no transaction wrapping the operation in Django's `DomainService` — if Django deletes a `Domain` object via ORM, the cascade happens at the DB level, but Django's in-memory objects (cached queries, signal handlers) are not aware. If the delete is rolled back in Django but not at the DB level (possible with `managed = False`), state is inconsistent.
**Trigger:** Deleting a domain via Django ORM without proper transaction handling.
**Fix:** Ensure all domain deletions are wrapped in `transaction.atomic()` and cross-check Django and DB state.

---

## EC-19: Missing Index on `aliases.destination`
**File:** `init-db.sh:79`
**Risk:** Low — Performance
**Description:** `idx_aliases_lookup` only indexes `(domain_id, source)`. Postfix also looks up aliases by destination (for catch-all and wildcard expansions), but there is no index on `destination`.
**Trigger:** Thousands of alias records with destination-based lookups.
**Fix:** Add `CREATE INDEX idx_aliases_destination ON aliases(destination)`.

---

## EC-20: No UUID Validation Before DB Queries
**Files:** `services/*.py` (various)
**Risk:** Medium — SQL injection vector (though mitigated by parameterized queries)
**Status:** ✅ Fixed — Added max-length validation at UserService and DomainService boundaries
**Description:** Service methods accept domain names and email addresses as raw strings. While Django ORM parameterizes queries, the lack of input validation before query construction means that extremely long strings (e.g., 10KB domain names) or non-printable characters can cause unexpected behavior, DB timeouts, or index bloat.
**Trigger:** Passing a 10,000-character domain name to `DomainService.get_domain_by_name()`.
**Fix:** Add input validation with max-length enforcement at service layer boundaries.

---

## EC-21: Race Condition on Mailbox/Domain get_or_create
**Files:** `accounts/views.py:setup_advance`, `accounts/views.py:_create_first_account`
**Risk:** Medium — Duplicate key violations
**Description:** `Domain.objects.get_or_create(name=domain)` and `Mailbox.objects.get_or_create(domain=domain, local_part=local_part)` are called during setup. Under concurrent requests (unlikely but possible), the `get_or_create` can race and throw an `IntegrityError` because `get_or_create` is not atomic in PostgreSQL under the default `READ COMMITTED` isolation level when using `managed = False` models.
**Trigger:** Two admin users completing setup simultaneously.
**Fix:** Wrap in `transaction.atomic()` and catch `IntegrityError`, or use `SELECT ... FOR UPDATE` within a manual transaction.

---

## EC-22: No Default Ordering on Alias Model
**File:** `mail/models.py:34-37`
**Risk:** Low — Non-deterministic query results
**Description:** The `Alias` model has no `Meta.ordering`, unlike `Domain` (order by name) and `StoredFile` (order by created_at). Queries against `Alias` without explicit ordering may return results in unpredictable order.
**Trigger:** Paginated alias display without explicit `order_by()`.
**Fix:** Add `ordering = ["domain", "source"]` to Alias Meta.

---

## EC-23: Quota Bytes Defaults to 0 (Zero = Unlimited) — Ambiguous
**File:** `mail/models.py:12`
**Risk:** Medium — Storage management
**Description:** `quota_bytes = models.BigIntegerField(default=0)`. A value of 0 means "no quota limit." However, there is no check anywhere in the codebase to enforce or report on mailbox quotas. The field exists but is never read by Postfix, Dovecot, or the Django admin. Mailboxes will grow unbounded.
**Trigger:** Mailbox grows until disk is full. No alerting when approaching quota.
**Fix:** Implement quota enforcement in Dovecot (`quota` plugin) and add quota monitoring/display to the dashboard.

---

## EC-24: `password_hash` Field in MailUser is Redundant/Confusing
**File:** `accounts/models.py:25`, `init-db.sh:30-32`
**Risk:** Low — Data confusion
**Description:** The `users` table has both a `password` (VARCHAR 128 for Dovecot) and `password_hash` (VARCHAR 512 for Django). Django uses `password_hash` via `AbstractBaseUser`, but Dovecot uses `password`. These two fields can get out of sync if only one is updated, causing login failures for either Dovecot or Django.
**Trigger:** Changing password from Django admin without updating the Dovecot password field.
**Fix:** Centralize password management so both fields are always updated together.

---

## EC-25: No Database-Level Default for `aliases` Table `id` Column
**File:** `init-db.sh:55`
**Risk:** Low — ID generation
**Description:** The `aliases` table has `id UUID PRIMARY KEY` but no `DEFAULT uuid_generate_v4()`. Depending on how inserts are performed (e.g., raw SQL inserts from Postfix), the ID may be `NULL` or fail.
**Trigger:** Raw SQL insert into `aliases` without specifying an ID.
**Fix:** Add `DEFAULT uuid_generate_v4()` to the `id` column.

---

## EC-26: No Database-Level Unique Constraint on `users.email`
**File:** `init-db.sh:38`
**Risk:** Medium — Data integrity
**Status:** ✅ Fixed — Added idempotent `UNIQUE` constraint via DO block
**Description:** The `users` table has `UNIQUE(email)` at line 38, but `ALTER TABLE` statements later (lines 41-44) don't re-assert this. If an earlier migration failed partially, the unique constraint might be missing. Django's `MailUser.email` has `unique=True`, but `managed = False` means Django never validates this.
**Trigger:** Manual DB operations that bypass Django ORM.
**Fix:** Make the unique constraint creation idempotent via `CREATE UNIQUE INDEX IF NOT EXISTS`.

---

## EC-27: Application Name Not Set on All Connections
**File:** `init-db.sh:80-81`
**Risk:** Low — Observability
**Description:** The `DOVECOT_DB_PASSWORD` and `POSTFIX_DB_PASSWORD` roles have no `application_name` set in their connection strings. When troubleshooting database connections, it's impossible to distinguish a Postfix connection from a Dovecot connection in `pg_stat_activity`.
**Trigger:** Database connection troubleshooting.
**Fix:** Set `application_name` in Postfix and Dovecot PostgreSQL lookup configs.

---

## EC-28: No Read Replica or Connection Failover
**File:** `settings/base.py:81-97`
**Risk:** Medium — Availability
**Description:** The database configuration defines a single `default` database with no read replicas, connection pooling (PgBouncer), or automatic failover. If PostgreSQL becomes unavailable, the entire application (including health checks) goes down.
**Trigger:** PostgreSQL container restart, crash, or maintenance.
**Fix:** Add connection pooling via PgBouncer sidecar and configure database routing for reads.

---

## EC-29: Missing `ON DELETE SET NULL` for StoredFile Entity References
**File:** `core/storage/models/stored_file.py:20-21`
**Risk:** Medium — Orphaned file records
**Description:** `StoredFile.entity_id` is a nullable UUID with no foreign key constraint. When the referenced entity (e.g., a Product or User) is deleted, the `StoredFile` records remain orphaned — pointing to a non-existent entity. There is no cleanup mechanism.
**Trigger:** Deleting an entity that has associated stored files.
**Fix:** Add a cleanup signal or cascade delete logic in the service layer.

---

## EC-30: Missing Database Health Check in Entrypoint Wait Loop
**File:** `entrypoint.sh:18-29`
**Risk:** Medium — Startup race
**Description:** The entrypoint wait loop only checks PostgreSQL connectivity. It does not check whether the `init-db.sh` has completed (i.e., tables and roles exist). If the init script takes longer than the 60-second wait window, Django migrations will fail because the `ifinmail_app` role or tables may not exist yet.
**Trigger:** First-time deployment on slow hardware.
**Fix:** Add a check for the existence of the `domains` table or the `ifinmail_app` role before declaring the database "ready."
**Fix:** Add a check for the existence of the `domains` table or the `ifinmail_app` role before declaring the database "ready."
**Fix:** Add a check for the existence of the `domains` table or the `ifinmail_app` role before declaring the database "ready."

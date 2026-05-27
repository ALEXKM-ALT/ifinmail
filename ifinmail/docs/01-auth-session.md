# Authentication & Session Security — Edge Cases (1–15)

## EC-01: Session Fixation via Unchanged Session ID on Login
**File:** `accounts/views.py:login_view`
**Risk:** High — Session hijacking
**Description:** The `login_view` calls `authenticate()` then `login()`, but there is no explicit `request.session.cycle_key()`. Django's `login()` does cycle the session, but only if the user's `SESSION_COOKIE_AGE` and related settings are respected. If middleware order is wrong or if a CSRF token is stolen before login, the old session persists.
**Trigger:** Attacker tricks user into authenticating with a known session ID.
**Fix:** Call `request.session.cycle_key()` before `login()`.

---

## EC-02: Empty Password on Superuser Creation
**File:** `entrypoint.sh:52-54`
**Risk:** Critical — Unauthenticated admin access
**Description:** The `entrypoint.sh` creates a superuser if `DJANGO_SUPERUSER_USERNAME` and `DJANGO_SUPERUSER_PASSWORD` are set. However, it does not validate that the password is non-empty. An empty `DJANGO_SUPERUSER_PASSWORD` results in a Django superuser with an empty password hash, which may match empty-string authentication attempts.
**Trigger:** `DJANGO_SUPERUSER_PASSWORD=""` in `.env` file.
**Fix:** Validate password length > 8 and non-empty before createsuperuser.

---

## EC-03: Brute-Force Bypass via Axes Lockout Reset on Success
**File:** `settings/base.py:156`
**Risk:** Medium — Brute-force amplification
**Description:** `AXES_RESET_ON_SUCCESS = True` means a successful login globally resets the failure count for that IP **and** username. An attacker who knows the password can interleave login attempts: 4 failures, then 1 success, then 4 more failures without ever hitting the 5-failure lockout. This resets the window indefinitely.
**Trigger:** Interleaving valid + invalid credentials in a single session.
**Fix:** Either disable `AXES_RESET_ON_SUCCESS` or add IP-level tracking that persists across successful logins for the duration of `AXES_COOLOFF_TIME`.

---

## EC-04: No Rate Limiting on Password Reset / Session Enumeration
**File:** No password reset endpoint exists
**Risk:** Medium — Account enumeration
**Description:** There is no password reset flow implemented at all. This means a user who forgets their password has no recovery path. When a reset flow is added, it must rate-limit attempts and not reveal whether an email is registered.
**Trigger:** Admin loses credentials — no recovery path exists.
**Fix:** Implement a rate-limited password reset flow with constant-time responses.

---

## EC-05: Next URL Open Redirect on Login
**File:** `accounts/views.py:40`
**Risk:** Medium — Phishing / Open redirect
**Description:** The `login_view` accepts a `next` GET parameter and redirects to it without validation. An attacker can craft `https://ifinmail.example.com/accounts/login/?next=https://evil.com/phish` and use it in phishing campaigns.
**Trigger:** `next` parameter points to external domain.
**Fix:** Use `django.utils.http.url_has_allowed_host_and_scheme()` to validate the redirect target, or restrict to relative URLs only.

---

## EC-06: No Account Lockout Notification
**File:** `accounts/views.py:31-43`
**Risk:** Low — User experience
**Description:** When Axes locks out a user after 5 failed attempts, the login page returns a generic "Invalid email or password" error. The user has no way to know they are locked out versus simply having wrong credentials.
**Trigger:** User exceeds `AXES_FAILURE_LIMIT` (5).
**Fix:** Check `axes.helpers.is_locked()` and show a specific lockout message with unlock time.

---

## EC-07: Session Not Invalidated on Logout Across All Tabs
**File:** `accounts/views.py:logout_view`
**Risk:** Medium — Session persistence
**Description:** Django's `logout()` flushes the session, but if the session backend is `cached_db`, and the user has multiple tabs open, a concurrent request in another tab may have loaded the session data into local memory before the flush. That tab's subsequent requests will still carry the old session cookie until it's forced to re-fetch from the backend.
**Trigger:** Multiple tabs open during logout.
**Fix:** Override `SESSION_ENGINE` behavior to force session flush on every request after logout.

---

## EC-08: Staff Check Does Not Revalidate Session
**File:** `accounts/views.py:_is_staff`
**Risk:** Medium — Privilege escalation
**Description:** The `_is_staff` helper is called on every decorator-gated view via `user_passes_test`. However, if a user is demoted from staff to regular user while their session is active, the decorator does not re-check permissions from the database on every request — it relies on the cached `user` object in the session.
**Trigger:** Admin demotes a staff user; that user's session is still valid.
**Fix:** Use a `request.user.is_active` and re-fetch from DB on every staff-checked view, or reduce `SESSION_COOKIE_AGE` to force re-authentication.

---

## EC-09: No 2FA / MFA Support
**File:** Not implemented
**Risk:** High — Account compromise
**Description:** The Django admin panel has no multi-factor authentication. If the admin password is compromised (phishing, credential stuffing, breach), an attacker gains full control of the email server.
**Trigger:** Password compromised.
**Fix:** Integrate `django-otp` or a similar MFA library.

---

## EC-10: CSRF Protection Disabled for API Endpoints
**File:** Not currently an issue, but architecture risk
**Risk:** Medium — CSRF on future API endpoints
**Description:** The project uses `django-ninja` for API endpoints (or may in the future). django-ninja does not enforce CSRF by default for non-session authentication. If bearer tokens or API keys are not properly implemented, CSRF attacks can execute privileged actions.
**Trigger:** Future API endpoint without CSRF protection.
**Fix:** Ensure all state-changing API views enforce either CSRF or token-based authentication.

---

## EC-11: Setup Wizard Allows Re-Execution After Completion
**File:** `accounts/views.py:setup_advance`
**Risk:** High — Re-provisioning attack
**Description:** The setup wizard checks `request.session.get("setup_complete")` and redirects to dashboard if set. But the check is session-based, not database-backed. An attacker who clears their session cookies can re-run the entire setup wizard, including creating a new admin account and overwriting domain settings.
**Trigger:** Clearing browser session cookies and navigating to `/accounts/setup/`.
**Fix:** Add a database flag (`SiteConfiguration.setup_complete`) that persists beyond sessions.

---

## EC-12: Setup Wizard Stores API Tokens Unencrypted in Session
**File:** `accounts/views.py:setup_advance:390`
**Risk:** Medium — Credential leak
**Description:** DNS provider API tokens are stored in `request.session["setup_dns_token"]` as raw plaintext. Django sessions are encrypted at rest (if using `cached_db` backend), but the token remains in the session object accessible via server-side debugging, logs, and database inspection.
**Trigger:** Session database compromised; debug logging enabled.
**Fix:** Store tokens only in `DNSProviderConfig` model with encryption at rest, not in the session.

---

## EC-13: No Audit Trail for Login Attempts (Success or Failure)
**File:** `accounts/views.py:login_view`
**Risk:** Medium — Forensics / Incident response
**Description:** Successful and failed login attempts are not recorded in the `AuditService`. Only Axes tracks failures internally, but there is no centralized audit event for authentication events. Security investigators cannot review login history.
**Trigger:** Security incident requiring login history review.
**Fix:** Add `AuditService.record()` calls for both successful and failed login attempts.

---

## EC-14: In-Memory Audit Log Lost on Restart
**File:** `services/audit.py`
**Risk:** High — Audit trail loss
**Description:** The `AuditService._events` list is an in-memory Python list with a max of 500 events. Any service restart (deploy, crash, scaling) wipes the entire audit trail. Events are never persisted to the database.
**Trigger:** Any container restart, including deploys.
**Fix:** Persist audit events to a database table or at minimum to structured log shipping.

---

## EC-15: Permission Check `has_perm` Returns True Only for Superusers
**File:** `accounts/models.py:43-44`
**Risk:** Medium — Overly restrictive by design
**Description:** `MailUser.has_perm()` always returns `False` unless the user is a superuser. This means Django's built-in permission system cannot be used for granular access control — any staff user who is not a superuser will be denied all permissions. This forces an all-or-nothing security model.
**Trigger:** Attempting to grant limited admin access to non-superuser staff.
**Fix:** Implement proper Django permission support for staff users with granular model-level permissions.

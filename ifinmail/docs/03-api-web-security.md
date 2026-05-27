# API & Web Security — Edge Cases (31–45)

## EC-31: No Validation of `page` Parameter in Domain Paginator
**File:** `accounts/views.py:246`
**Risk:** Medium — Parameter injection
**Description:** The `request.GET.get("page", 1)` parameter is passed directly to `Paginator.get_page()`. While Django's paginator handles non-integer values gracefully (returns page 1), extreme values like negative numbers or `page=99999999` can cause unnecessary database load (full table scan to count) and potential denial of service.
**Trigger:** Sending `?page=99999999` to the dashboard.
**Fix:** Clamp the page parameter to a reasonable maximum (e.g., `min(max(int(page), 1), 1000)`).

---

## EC-32: Health Check Endpoints Expose Internal Service Details
**Files:** `config/urls.py:health_dns`, `config/urls.py:health_deliverability`
**Risk:** Low — Information disclosure
**Description:** The `/health/dns/` and `/health/deliverability/` endpoints are unauthenticated and reveal DNS record status (which domain records pass/fail), SPF/DKIM/DMARC configuration details, and server IP address. This information aids attackers in profiling the mail infrastructure.
**Trigger:** Any unauthenticated request to health endpoints.
**Fix:** Require authentication for detailed health endpoints, or move them to internal-only paths.

---

## EC-33: No Input Size Limits on Autoconfig XML Endpoints
**Files:** `mail/views.py:autoconfig_mozilla`, `mail/views.py:autoconfig_outlook`
**Risk:** Low — Response size attack
**Description:** The autoconfig XML is generated using environment variables with no output encoding or size validation. Extremely long `MAIL_HOSTNAME` or `DOMAIN` values could produce XML responses large enough to cause memory issues on the API container.
**Trigger:** `MAIL_HOSTNAME` set to a 10,000-character string.
**Fix:** Add max-length validation to environment variable inputs used in response generation.

---

## EC-34: Autoconfig XML Has No XML Sanitization (XEE Injection)
**Files:** `mail/views.py:26-48, 56-81`
**Risk:** Low — XML External Entity (XXE) not exploitable here but architecture concern
**Status:** ✅ Fixed — Added `xml.sax.saxutils.escape()` for all interpolated values
**Description:** The XML responses are hand-crafted f-strings. If any environment variable contained XML special characters like `&`, `<`, `>`, the output would be malformed XML, potentially breaking email client configuration. While user input doesn't directly control these, environment variable misconfiguration could corrupt the XML.
**Trigger:** `MAIL_HOSTNAME` containing `&` or `<` characters.
**Fix:** Use an XML builder library or at minimum XML-escape the interpolated values.

---

## EC-35: No Cache Busting on Static Files
**Files:** Nginx config serves static files with `expires 30d` and `immutable`
**Risk:** Medium — Stale assets after deployment
**Status:** ✅ Fixed — Added `ManifestStaticFilesStorage` in production settings
**Description:** Static files are served with `Cache-Control: public, immutable` and `expires 30d`. After a deployment that changes CSS/JS files, browsers will continue to serve the cached versions for up to 30 days unless `collectstatic` generates new hashed filenames. The current `collectstatic` invocation does not use `--link` or manifest storage.
**Trigger:** Deploying CSS/JS changes.
**Fix:** Use Django's `ManifestStaticFilesStorage` to generate content-hashed filenames.

---

## EC-36: DNS Configuration Stores API Tokens in Plaintext
**File:** `dns/views.py:145-148`
**Risk:** High — Credential exposure
**Description:** `DNSProviderConfig.objects.update_or_create(provider=provider_name, defaults={"credentials": creds})` stores API tokens as-is in the `credentials` JSONField of the database. There is no encryption at rest. If the database is compromised, all DNS provider API tokens are exposed.
**Trigger:** Database dump or SQL injection.
**Fix:** Encrypt credentials at rest using Django's `django-cryptography` or Django's signing utilities.

---

## EC-37: DNS API Tokens Transmitted in Plaintext POST Body
**File:** `dns/views.py:139`
**Risk:** Medium — Credential interception
**Description:** DNS provider API tokens are sent as form POST parameters over HTTPS (which is encrypted in transit). However, they are logged in Django request logs (if DEBUG-level logging is enabled) and in nginx access logs as part of the request body.
**Trigger:** Debug logging enabled; nginx access log review.
**Fix:** Ensure credentials are never logged: sanitize POST parameters in logging middleware and nginx log_format.

---

## EC-38: DNS Provider Credentials Not Re-validated on Each Use
**File:** `dns/views.py:86-91`
**Risk:** Medium — Stale credentials
**Description:** `_get_provider()` loads credentials from the database that were valid at the time of configuration. If a provider revokes the API token or the user updates it, the stored credentials become invalid but there is no mechanism to detect or alert on this. The DNS status page will still show "configured" even though API calls fail.
**Trigger:** API token expired or revoked at the provider.
**Fix:** Add a credential validation step that tests the provider API connection when loading credentials, and flag invalid credentials on the dashboard.

---

## EC-39: No CSRF Protection on DNS `dns_configure` POST Endpoint
**File:** `dns/views.py:127-165`
**Risk:** Medium — CSRF attack on DNS configuration
**Description:** The `dns_configure` view is decorated with `@require_POST` and `@login_required`, but there is no `@csrf_protect` decorator, and Django's CSRF middleware does not apply by default to class-based views or when the middleware is misordered. An attacker could craft a cross-site request to modify DNS records.
**Trigger:** Admin visits attacker's page while authenticated to ifinmail.
**Fix:** Ensure `CsrfViewMiddleware` is in the middleware list and add `@csrf_protect` to the view, or use `django.views.decorators.csrf.ensure_csrf_cookie`.

---

## EC-40: Health Check Endpoint Lacks Rate Limiting
**File:** `config/urls.py:health_check`
**Risk:** Low — Accidental DDoS
**Description:** The `/health/` endpoint is unauthenticated and has no rate limiting in nginx. A monitoring system or load balancer that polls too aggressively (e.g., every second) combined with the database query (`SELECT 1`) can add unnecessary load. This is minor but worth noting as the number of monitored instances grows.
**Trigger:** Multiple monitoring systems polling every second.
**Fix:** Add a dedicated nginx `limit_req` zone for health endpoints, or serve a static health response from nginx directly without proxying to Django.

---

## EC-41: No `403` or `400` Custom Error Handlers
**File:** `config/urls.py:99-117`
**Risk:** Low — Inconsistent error responses
**Description:** Only `handler404` and `handler500` are defined. `handler403` (CSRF failure, permission denied) and `handler400` (bad request) are unhandled, returning Django's default HTML error pages that can leak framework version information.
**Trigger:** CSRF token mismatch; invalid request.
**Fix:** Add `handler400` and `handler403` custom JSON error handlers.

---

## EC-42: No Input Sanitization in Setup Wizard Domain Field
**File:** `accounts/views.py:375-376`
**Risk:** Medium — Domain validation
**Description:** The setup wizard accepts any string as a domain name (`domain = request.POST.get("domain", "").strip()`). No validation checks for valid DNS name format (no underscores, no spaces, valid TLD, no protocol prefixes). Creating a domain like `http://evil.com` in the database causes errors downstream in DNS record generation.
**Trigger:** User enters `https://example.com` or `not a domain` in the setup wizard.
**Fix:** Add domain name validation using a regex or Django's `URLValidator` with scheme check, and normalize to lowercase.

---

## EC-43: Server IP Detection Uses External Service Without Fallback Failure Handling
**File:** `dns/views.py:_get_server_ip`
**Risk:** Medium — DNS misconfiguration
**Description:** The `_get_server_ip()` function contacts `api.ipify.org` to determine the public IP. If that service is unreachable, it falls back to `socket.gethostbyname(socket.gethostname())`, which returns the container's internal IP (e.g., `172.x.x.x`) rather than the public IP. DNS records are then created pointing to the internal IP, breaking email delivery.
**Trigger:** Internet connectivity issue during provisioning; ipify.org service disruption.
**Fix:** Cache the server IP persistently after first successful detection, add multiple IP detection backends, and warn the user if the detected IP looks like a private address.

---

## EC-44: Legacy `/admin/` Redirect Could Create Redirect Loop
**File:** `config/urls.py:76-77, 86-87`
**Risk:** Low — UX issue
**Status:** ✅ Fixed — Redirected `/admin/` directly to dashboard via `reverse()`
**Description:** The `/admin/` and `/admin/<path:path>` URLs redirect to `/accounts/<path>`. If path is empty, it redirects to `/accounts/` which is itself a `RedirectView` to `/accounts/dashboard/`. This double-redirect works but adds latency and may confuse some HTTP clients that don't follow redirects.
**Trigger:** Navigating to `/admin/`.
**Fix:** Redirect `/admin/` directly to `/accounts/dashboard/` or `/manage-panel/`.

---

## EC-45: No `Content-Length` or `Content-Encoding` Validation
**File:** Not directly implemented
**Risk:** Low — Request smuggling (theoretical)
**Description:** Nginx proxies requests to the Django API container. If the `Content-Length` header differs from the actual body size, request smuggling or HTTP desync attacks are theoretically possible. Nginx's proxy configuration does not explicitly strip or validate `Transfer-Encoding` or `Content-Length` on incoming requests.
**Trigger:** Crafted HTTP request with mismatched Content-Length.
**Fix:** Ensure nginx strips `Transfer-Encoding: chunked` on HTTP/1.0 upstreams and validates content length against `client_max_body_size`.
**Fix:** Ensure nginx strips `Transfer-Encoding: chunked` on HTTP/1.0 upstreams and validates content length against `client_max_body_size`.

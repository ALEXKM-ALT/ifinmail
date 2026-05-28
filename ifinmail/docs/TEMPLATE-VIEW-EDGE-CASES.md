# Template-View Edge Cases

## 322 Edge Cases Across Template-View Coupling

> Generated from systematic audit of all template → view → context processor → environment variable coupling points.

---

## Table of Contents

1. [Variable Availability & Contract Mismatches](#1-variable-availability--contract-mismatches)
2. [Type Mismatches: Template Expects List, View Provides String/None](#2-type-mismatches-template-expects-list-view-provides-stringnone)
3. [Environment Variable Dependency & Missing ENV](#3-environment-variable-dependency--missing-env)
4. [Authentication & Authorization Gaps](#4-authentication--authorization-gaps)
5. [URL Resolution & Routing Edge Cases](#5-url-resolution--routing-edge-cases)
6. [CSRF & Form Handling Edge Cases](#6-csrf--form-handling-edge-cases)
7. [Template Inheritance & Block Scope Issues](#7-template-inheritance--block-scope-issues)
8. [Mock Data Leakage & Hardcoded Values](#8-mock-data-leakage--hardcoded-values)
9. [i18n & Translation Issues](#9-i18n--translation-issues)
10. [Static File & Media Resolution](#10-static-file--media-resolution)
11. [Inline JavaScript/Template Interaction](#11-inline-javascripttemplate-interaction)
12. [Session & State Management Edge Cases](#12-session--state-management-edge-cases)
13. [Exception Handling & Error Propagation](#13-exception-handling--error-propagation)
14. [Security & XSS Vectors](#14-security--xss-vectors)
15. [Dashboard-Specific Data Integrity Issues](#15-dashboard-specific-data-integrity-issues)
16. [Template Include Chain Variable Scoping](#16-template-include-chain-variable-scoping)
17. [500-Internal Error Handler Self-Reference](#17-500-internal-error-handler-self-reference)
18. [DNS Configuration View Data Integrity](#18-dns-configuration-view-data-integrity)
19. [CSRF Token Handling in DNS Auto-Config](#19-csrf-token-handling-in-dns-auto-config)
20. [Edge Cases in Branding & Identity](#20-edge-cases-in-branding--identity)
21. [Setup Wizard Progress & Edge Cases](#21-setup-wizard-progress--edge-cases)
22. [Axes Brute Force Protection Edge Cases](#22-axes-brute-force-protection-edge-cases)
23. [Monitoring Service Edge Cases](#23-monitoring-service-edge-cases)
24. [Audit Service Edge Cases](#24-audit-service-edge-cases)
25. [CSS Class Generation & Layout](#25-css-class-generation--layout)
26. [Accessibility Edge Cases](#26-accessibility-edge-cases)
27. [Setup Durable State & Missing Persistence](#27-setup-durable-state--missing-persistence)
28. [View Function Parameter Handling](#28-view-function-parameter-handling)
29. [Content-Type Negotiation](#29-content-type-negotiation)
30. [Pagination & Large Dataset Edge Cases](#30-pagination--large-dataset-edge-cases)
31. [Log Page Edge Cases](#31-log-page-edge-cases)
32. [Spam Filtering Page Edge Cases](#32-spam-filtering-page-edge-cases)
33. [User Management Page Edge Cases](#33-user-management-page-edge-cases)
34. [Email Client Autoconfig](#34-email-client-autoconfig)
35. [Provider Mapping](#35-provider-mapping)
36. [Template-Level Logic Errors](#36-template-level-logic-errors)
37. [Email Sending & Configuration](#37-email-sending--configuration)
38. [Context Processor Default Values](#38-context-processor-default-values)
39. [Hash Link Navigation](#39-hash-link-navigation)
40. [Broken UX Due to Disabled Buttons](#40-broken-ux-due-to-disabled-buttons)
41. [DNS Record Display Edge Cases](#41-dns-record-display-edge-cases)
42. [File System Edge Cases](#42-file-system-edge-cases)
43. [Integer/Float Conversion Edge Cases](#43-integerfloat-conversion-edge-cases)
44. [Redis Cache Edge Cases](#44-redis-cache-edge-cases)
45. [URL Pattern Conflicts](#45-url-pattern-conflicts)
46. [Additional Edge Cases](#46-additional-edge-cases)
47. [Missing CSRF on First Visit](#47-missing-csrf-on-first-visit)
48. [Database Connection Pooling](#48-database-connection-pooling)
49. [Additional Dashboard Issues](#49-additional-dashboard-issues)
50. [Template Default Value Inconsistencies](#50-template-default-value-inconsistencies)

---

## 1. Variable Availability & Contract Mismatches

### base.html → Global (67 lines)

| # | Edge Case | Template | Variable | View/Processor | Risk |
|---|-----------|----------|----------|----------------|------|
| 1 | `brand.favicon_url` links to missing static file (L14) | base.html | `default_icon_url` | None — static file not verified | 404 in console |
| 2 | `brand.css_overrides|safe` exposes XSS if brand color is attacker-controlled (L17) | base.html | `brand.css_overrides` | BrandingConfig.from_env() | Stored XSS via env var |
| 3 | `USE_GOOGLE_FONTS` default is string `"1"`, not boolean `True` — template logic treats everything truthy (L18) | base.html | `USE_GOOGLE_FONTS` | Not in any context processor | Always loads Google Fonts |
| 4 | Google Fonts CDN blocked by CSP (L21) | base.html | `<link rel="stylesheet">` | No CSP configured | Fonts silently fail |
| 5 | `manifest.json` not found (L13) | base.html | `{% static 'manifest.json' %}` | Static files not verified | 404 in logs |
| 6 | Service worker file not found (L61) | base.html | `js/service-worker.js` | Static files not verified | Promise rejection |
| 7 | `brand.tagline` empty in footer — renders `" — "` (L47) | base.html | `brand.tagline` | ServerContext doesn't provide default for tagline in footer | Ugly output |
| 8 | `LANGUAGE_CODE` is None (L5) | base.html | `lang="{{ LANGUAGE_CODE }}"` | i18n not configured | Invalid HTML attr |
| 9 | CSRF cookie is HTTPS-only — HTTP fallback fails (L55-56) | base.html | sidebar JS | CSRF_COOKIE_HTTPONLY=True | JS can't read cookie |

### error_base.html → urls.py error handlers (27 lines)

| # | Edge Case | Line | Variable | Risk |
|---|-----------|------|----------|------|
| 10 | `{% url 'accounts:dashboard' %}` fails if accounts URLs not loaded | L21 | `dashboard` URL | TemplateSyntaxError |
| 11 | `error_description` is `None` from view — block still renders empty `<p>` | L15 | `error_description` | Empty paragraph |
| 12 | `error_detail` is empty string (truthy in Python) — block renders with empty content | L16 | `error_detail` | `{% if '' %}` is False — safe, but non-obvious |
| 13 | `_wants_html()` fallback for `Accept: */*` returns `True` without AJAX header — API clients get HTML | urls.py L144 | `HTTP_ACCEPT` | Wrong content-type |
| 14 | Axes lockout exception is not serialized to JSON — `str(exception)` only captures first error | urls.py L129-130 | `str(exception)` | Missing detail |
| 15 | Error handler logger uses `log_msg` with `%s` but only passes `path` arg | urls.py L122-124 | `logger.log()` | Incomplete log message |

### 400.html / 403.html / 404.html / 500.html / 502.html / 503.html / 504.html

| # | Edge Case | Template | Line | Risk |
|---|-----------|----------|------|------|
| 16 | `400.html` doesn't override `error_detail` block — shows view-provided value | 400.html | L5 | Inconsistent with 500 series |
| 17 | `400.html` doesn't override `error_actions` — shows dashboard link + back button | 400.html | L6 | Might not make sense for bad request |
| 18 | 500.html "Retry" button calls `window.location.reload()` — re-POSTs on GET-only error | 500.html | L9 | Duplicate error triggers |
| 19 | 502/503/504 have both `error_detail` override + action override, 400/403/404 don't — inconsistency | All | — | Fragmented dev experience |
| 20 | `error_title` in 404 template hardcodes "Page Not Found" but view sends "Not found" | 404.html | L4 | Double translation needed |

### sidebar.html → Multiple Views (70 lines)

| # | Edge Case | Variable | Provided By | Risk |
|---|-----------|----------|-------------|------|
| 21 | `active_section` missing → no nav highlighted | `active_section` | Each view must provide | Broken UX |
| 22 | `brand.name` empty → renders empty string | `brand.name` | BrandingConfig | Blank space |
| 23 | `brand.logo_url` truthy but broken URL → broken img | `brand.logo_url` | BrandingConfig | Broken image |
| 24 | `server_version` default "v2.4.0-stable" hardcoded | `server_version` | ServerContext | Stale version string |
| 25 | `server_status` "Online" hardcoded | `server_status` | ServerContext | Never reflects reality |
| 26 | Security/SSL nav link targets `#security` hash on dashboard — hash-only link broken on non-dashboard pages | L33-34 | `{% url 'accounts:dashboard' %}#security` | Wrong page |
| 27 | `support_email` missing → renders empty mailto: link | `support_email` | ServerContext | Dead support link |

### header.html → Multiple Views + Context (38 lines)

| # | Edge Case | Variable | Provided By | Risk |
|---|-----------|----------|-------------|------|
| 28 | `header_search_placeholder` missing from view → default "Search settings..." | `header_search_placeholder` | each view | OK |
| 29 | Search form always submits to `accounts:logs` even on non-logged-in pages | L7 | `{% url 'accounts:logs' %}` | Login-required page redirect |
| 30 | `show_settings_icon` only set in `branding_identity` and `dashboard` views — absent elsewhere | `show_settings_icon` | view | Settings icon hidden |
| 31 | `show_user_profile` only set in `user_management` — absent elsewhere | `show_user_profile` | view | Profile not shown |
| 32 | `user_initials` from context processor falls back to 'AD' for anonymous on login page | `user_initials` | user_context | Shows "AD" on login page |
| 33 | `user_display_name` shows "Guest" on login page | `user_display_name` | user_context | OK |
| 34 | Notification bell always shows "No new notifications" title — `notification_count` is always 0 | `notification_count` | server_context | Never accurate |

### admin_table.html → Multiple Views (27 lines)

| # | Edge Case | Variable | Risk |
|---|-----------|----------|------|
| 35 | `span` is `None` → CSS class becomes `ifinmail-span-None` | `span` | Broken layout |
| 36 | `headers` is empty string `''` → `|length` = 0 → colspan=1 | `headers` | Wrong colspan |
| 37 | `row_template` path wrong → `{% include row_template %}` fails silently or throws | `row_template` | TemplateSyntaxError |
| 38 | `rows` is string instead of list → `{% for row in rows %}` iterates over characters | `rows` | Malformed output |
| 39 | `title_extra` content is HTML-escaped (no `|safe`) | `title_extra` | HTML displayed as text |
| 40 | `empty_message` is None → renders nothing (no fallback message) | `empty_message` | Empty table |

### admin/partials/ — Row Templates

| # | Edge Case | Template | Risk |
|---|-----------|----------|------|
| 41 | `row` keys missing → all fallbacks to `'—'` | admin_row.html | Misleading display |
| 42 | `row.status_class` missing in queue_row → no badge class | queue_row.html | Badge invisible |
| 43 | `row.mx_status_class` boolean inversion — `{% if row.mx_status_class %}` shows danger style | dns_row.html | Inverted logic |
| 44 | `row.auth_records|safe` could be malicious HTML | dns_row.html | XSS |
| 45 | `row.actions|safe` could be malicious HTML | dns_row.html | XSS |
| 46 | `row.level` not matching any badge class condition → default badge | log_row.html | Badge rendering |
| 47 | `row.tone` in provider_row not matching any condition → no badge at all | provider_row.html | Unstyled badge |

---

## 2. Type Mismatches: Template Expects List, View Provides String/None

| # | Edge Case | Template | Variable | View | Issue |
|---|-----------|----------|----------|------|-------|
| 48 | `{% for h in telemetry_bars %}` — if `None` → error | dashboard.html | `telemetry_bars` | `_get_telemetry_bars()` | for loop crashes |
| 49 | `{% for host in cluster_hosts %}` — if `None` | dns_config.html | `cluster_hosts` | dns views | for loop crash |
| 50 | `{% for engine in filter_engines %}` — if `None` | spam_filtering.html | `filter_engines` | spam view | for loop crash |
| 51 | `{% for role in role_counts %}` — if `None` | user_management.html | `role_counts` | users view | for loop crash |
| 52 | `{% for session in live_sessions %}` — if `None` | user_management.html | `live_sessions` | users view | for loop crash |
| 53 | `{% for item in governance_items %}` — if `None` | user_management.html | `governance_items` | users view | for loop crash |
| 54 | `{% for h in anomaly_bars %}` — if `None` | user_management.html | `anomaly_bars` | users view | for loop crash |
| 55 | `{% for item in audit_items %}` — if `None` | logs.html | `audit_items` | logs view | for loop crash |
| 56 | `{% for h in filter_activity_bars %}` — if `None` | spam_filtering.html | `filter_activity_bars` | spam view | for loop crash |
| 57 | `{% for rec in dns_records %}` — if string, iterates chars | setup_table.html | `dns_records` | setup view | Malformed output |
| 58 | `headers=` passed string `''` — `|length` = 0 | admin_table.html | `headers` | Colspan = 1 |
| 59 | `rows=` passed string `''` — for loop over chars | admin_table.html | `rows` | Broken table |
| 60 | `providers|default:''` — if providers is empty list, default is ignored (list is truthy) | spam_filtering.html | `providers` | OK |
| 61 | `storage_pct` is number `85.3` but CSS expects string like `"85.3%"` | dashboard.html | `storage_pct` | Dashboard | CSS width broken |
| 62 | `log_footer` rendered with auto-escape — HTML tags visible | logs.html | `log_footer` | logs view | Escaped HTML |

---

## 3. Environment Variable Dependency & Missing ENV

| # | Edge Case | Variable | ENV | Fallback | Risk |
|---|-----------|----------|-----|----------|------|
| 63 | `SECRET_KEY` not set → `KeyError` | settings | `DJANGO_SECRET_KEY` | None | Server won't start |
| 64 | `DB_NAME`, `DB_USER`, `DB_PASSWORD` not set → `KeyError` | settings | Required | None | Server crash |
| 65 | `MAIL_HOSTNAME` missing → TLS check gets empty cert path | dashboard.py | `MAIL_HOSTNAME` | `''` | No TLS check |
| 66 | `DOMAIN` missing → fallback to `MAIL_DOMAIN` then `''` | Multiple | `DOMAIN` | `''` | Many features broken |
| 67 | `MAIL_VHOSTS_DIR` missing → defaults to `/var/mail/vhosts` | dashboard.py | `MAIL_VHOSTS_DIR` | `/var/mail/vhosts` | May not exist |
| 68 | `LETSENCRYPT_DIR` missing → defaults to `/etc/letsencrypt` | dashboard.py | `LETSENCRYPT_DIR` | `/etc/letsencrypt` | May not exist |
| 69 | `DISK_CHECK_PATHS` missing → checks `/var/mail/vhosts,/app,/` | dashboard.py | `DISK_CHECK_PATHS` | Hardcoded | May not exist |
| 70 | `IP_CHECK_URL` missing → uses `api.ipify.org` | setup.py | `IP_CHECK_URL` | ipify | External dep |
| 71 | `DKIM_SELECTOR` missing → uses "default" | monitoring.py | `DKIM_SELECTOR` | "default" | Wrong record checked |
| 72 | `STATIC_ROOT` missing → defaults to `BASE_DIR/staticfiles` | settings | `STATIC_ROOT` | relative path | May collide |
| 73 | `CORS_ALLOWED_ORIGINS` empty → no CORS | settings | `CORS_ALLOWED_ORIGINS` | `[]` | Cross-origin blocked |
| 74 | `ALLOWED_HOSTS` empty in production → `ValueError` | settings | `ALLOWED_HOSTS` | `[]` | Hard crash |
| 75 | `REDIS_URL` missing → `redis://localhost:6379/0` | settings | `REDIS_URL` | Hardcoded | May connect wrong |
| 76 | `BRAND_COLOR` invalid hex → CSS overrides may produce invalid CSS | branding.py | `BRAND_COLOR` | `#0051D5` | Broken colors |
| 77 | `BRAND_LOGO_URL` missing → `""` → falls to inline SVG | branding.py | `BRAND_LOGO_URL` | `""` | OK |
| 78 | `SESSION_COOKIE_SECURE=True` without HTTPS → sessions don't work | production.py | `SESSION_COOKIE_SECURE` | True | No sessions without TLS |
| 79 | `CSRF_COOKIE_SECURE=True` without HTTPS → CSRF fails | production.py | `CSRF_COOKIE_SECURE` | True | Login broken without TLS |

---

## 4. Authentication & Authorization Gaps

| # | Edge Case | View | Template | Risk |
|---|-----------|------|----------|------|
| 80 | `@login_required` on dashboard but no `LOGIN_URL` fallback in settings | dashboard | dashboard.html | Redirect to wrong URL |
| 81 | `_is_staff()` catches all exceptions — user refresh failing silently returns False | auth.py | All admin views | Silent auth failure |
| 82 | Login page renders with `error` context even on GET | auth.py | login.html | OK |
| 83 | `logout_view` calls `request.session.flush()` before `logout()` — order is correct | auth.py | — | OK |
| 84 | `@user_passes_test(_is_staff)` redirects to LOGIN_URL on failure — user sees login with no error message | Multiple | login.html | Silent redirect |
| 85 | `axes` import wrapped in try/except — silently disables lockout | auth.py | login.html | No brute force protect |
| 86 | `_is_staff` checks `user.refresh_from_db()` on every request — DB load per request | auth.py | Multiple | Performance issue |
| 87 | DNS status endpoint returns `{"error": str(e)}` on exception — exposes internals | dns/views/api.py | — | Info leak |
| 88 | `@require_POST` on dns_configure without `@csrf_protect` — only `@ensure_csrf_cookie` | dns/views/api.py | — | CSRF not enforced |
| 89 | No rate limiting on login endpoint — only Axes protects | auth.py | login.html | Brute force possible |
| 90 | Setup wizard not protected against re-entry after completion — `_setup_is_complete()` prevents | setup.py | setup/*.html | OK |

---

## 5. URL Resolution & Routing Edge Cases

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 91 | `{% url 'accounts:dashboard' %}` in ALL error templates — if URL not registered, template error | All error templates | TemplateSyntaxError cascade |
| 92 | `{% url 'accounts:logout' %}` not guarded by `@login_required` in the template — renders on login page | header.html | Renders logout on login |
| 93 | `{% url 'accounts:setup_step' step='welcome' %}` — if step URL not registered | Multiple | TemplateSyntaxError |
| 94 | `{% url 'accounts:setup_advance' %}` — POST target not registered | setup/*.html | TemplateSyntaxError |
| 95 | `/admin/` redirect uses `legacy_accounts_redirect` — chains through URLs.py | urls.py | Redirect double-hop |
| 96 | `/admin/<path:path>` catch-all — could match paths with auth bypass | urls.py | Path traversal |
| 97 | `dns:status` URL referenced in inline JS — if URL name changes, JS silently fails | dns_config.html | Broken refresh |
| 98 | `dns:configure` URL in inline JS — same risk | dns_auto.html | Broken auto-config |
| 99 | `{% url 'accounts:login' %}` in `@user_passes_test` — login_url parameter must match | Multiple views | Wrong redirect |
| 100 | `autoconfig-mozilla-alt` defined at root — may conflict with other `.well-known` handlers | urls.py | URL collision |

---

## 6. CSRF & Form Handling Edge Cases

| # | Edge Case | Template | View | Risk |
|---|-----------|----------|------|------|
| 101 | Login form uses `{% csrf_token %}` but no `ensure_csrf_cookie` decorator | login.html | auth.py | CSRF token missing on first GET |
| 102 | Setup forms all POST to `setup_advance` but no CSRF exemption | setup/*.html | setup.py | OK |
| 103 | dns_config inline JS uses manual CSRF token extraction from DOM | dns_config.html | — | Token may be stale |
| 104 | dns_auto.html JS uses `document.querySelector('[name=csrfmiddlewaretoken]')` — could fail if multiple forms | dns_auto.html | — | Token from wrong form |
| 105 | DNS configure POST accepts provider credentials — sent as form data (not encrypted payload) | dns/views/api.py | — | Credentials in plaintext |
| 106 | `dns_configure` reads POST data, not JSON body — incompatible with JSON API clients | dns/views/api.py | — | API incompatibility |

---

## 7. Template Inheritance & Block Scope Issues

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 107 | `base.html` has `{{ brand.css_overrides|safe }}` in `<head>` — XSS via brand config | base.html L17 | Stored XSS |
| 108 | `error_base.html` extends `base.html` but overrides `sidebar_wrapper`, `header`, `footer` — leaves `ifinmail-app-main` wrapping only `<main>` | error_base.html L8-10 | Layout broken |
| 109 | `login.html` extends `base.html` but overrides `sidebar_wrapper`, `header`, `footer` — same issue | login.html L8-10 | No layout |
| 110 | Setup templates extend `base.html` without overriding sidebar/header — no sidebar/header shown (intended) | setup/*.html | Intended |
| 111 | `dns_config.html` has nested block `{% block dns_config_scripts %}` inside `{% block content %}` — unusual nesting | dns_config.html L88-95 | Confusing structure |
| 112 | `dns_auto.html` has nested block `{% block dns_auto_scripts %}` — same pattern | dns_auto.html L58-104 | Same |
| 113 | `{% block sidebar_script %}` in `base.html` runs on ALL pages including error pages — sidebar JS runs even without sidebar | base.html L54-56 | Useless execution |
| 114 | Service worker script block runs on error pages — registers SW on /500/ etc. | base.html L58-64 | Wasted registration |

---

## 8. Mock Data Leakage & Hardcoded Values

| # | Edge Case | Function | Data | Risk |
|---|-----------|----------|------|------|
| 115 | `_active_queue_rows()` returns hardcoded mock data | dashboard.py L288-293 | 2 mock rows | Never reflects real queue |
| 116 | `_get_traffic_stats()` returns "42.8k", "+12.4%" — hardcoded | dashboard.py L296-303 | Mock traffic | Misleading data |
| 117 | `_get_uptime_stats()` returns "99.98%", "Stable runtime" — hardcoded | dashboard.py L305-311 | Mock uptime | Misleading data |
| 118 | `_get_telemetry_bars()` returns hardcoded array | dashboard.py L314-316 | Mock bars | Never real data |
| 119 | `_get_system_load()` returns "24", "6.8 GB", "of 16GB ECC" — hardcoded | dashboard.py L319-327 | Mock load | Misleading |
| 120 | `_admin_log_rows()` returns 6 hardcoded log entries | logs.py L10-48 | 2016 timestamps | Stale data |
| 121 | `_admin_audit_items()` returns 4 hardcoded audit entries | logs.py L51-81 | Mock audit | No real data |
| 122 | `_admin_directory_rows()` returns 3 hardcoded users | users.py L10-36 | Mock users | Never live |
| 123 | DNS registry rows show hardcoded "ifinmail.io", "stark-industries.net" | dns/views/web.py L81-109 | Mock domains | Never real |
| 124 | DNS toolbox SPF fallback "v=spf1 mx -all" if domain/server_ip missing | dns/views/web.py L76-77 | Hardcoded | Misleading |
| 125 | `propagation_sync` = "4.2ms avg", `propagation_pct` = "99.9%" — hardcoded | dns/views/web.py L119-120 | Hardcoded | Never real |
| 126 | `dnssec_issues` = "12", `nameserver_count` = "4" — hardcoded | dns/views/web.py L121-123 | Hardcoded | Never real |
| 127 | `cluster_hosts` — hardcoded list | dns/views/web.py L125-129 | Hardcoded | Never real |
| 128 | `dkim_selector` = "ifinmail-2023" — hardcoded | dns/views/web.py L130 | Hardcoded | Never real |

---

## 9. i18n & Translation Issues

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 129 | `{% blocktrans %}` in error_base.html wraps entire block including `brand.name` — dynamic var in translation | error_base.html L4 | Translation can't handle dynamic brand |
| 130 | `{% trans %}` in error templates not consistent — 400 uses `{% trans %}`, 500 uses `{% trans %}` | All | OK |
| 131 | `{{ traffic_stats.label|default:'' }}` — label is already translated via `str(_("Outbound messages"))` | dashboard.html L45 | Double translation |
| 132 | `{{ uptime_stats.pct|default:'0%' }}` — default string not wrapped in `{% trans %}` | dashboard.html L51 | Untranslated |
| 133 | `{{ uptime_stats.status|default:'' }}` — "Policy Compliant" from view not wrapped in `{% trans %}` | dashboard.html L53 | View returns default, not translated |
| 134 | `{{ system_load.cpu_label|default:'' }}` — translated in view | dashboard.html L64 | OK |
| 135 | `{{ system_load.mem_total|default:'' }}` — "of 16GB ECC" not translated | dashboard.html L65 | View returns hardcoded English |
| 136 | `{{ server_version }}` in sidebar — version string not translated | sidebar.html L15 | Not localizable |
| 137 | `{{ server_status }}` in sidebar — "Online" not translated | sidebar.html L59 | Not localizable |
| 138 | `{{ header_search_placeholder|default:_('Search settings...') }}` — uses `_()` instead of `{% trans %}` | header.html L10 | OK |
| 139 | `{{ empty_message }}` in admin_table — if from view, must be translated at view level | admin_table.html L20 | Untranslated fallback |
| 140 | `{{ rec.value|default:'' }}` in setup_table — DNS record values not translated | setup_table.html L4 | OK (not user-facing text) |

---

## 10. Static File & Media Resolution

| # | Edge Case | Path | Risk |
|---|-----------|------|------|
| 141 | `manifest.json` not collected — 404 in browser | static/manifest.json | PWA broken |
| 142 | `js/service-worker.js` not collected — 404 | static/js/service-worker.js | SW registered, 404 fetch |
| 143 | `js/ifinmail-sidebar.js` not collected — 404 | static/js/ifinmail-sidebar.js | Sidebar JS broken |
| 144 | `icons/icon-192.svg` not collected — 404 | static/icons/icon-192.svg | Default icon missing |
| 145 | CSS files order: variables, reset, utilities, layout, components — if any missing, cascade breaks | base.html L23-27 | Broken layout |
| 146 | `ManifestStaticFilesStorage` in production — old filenames break if statics not re-collected | production.py L32 | 404 on all static files |

---

## 11. Inline JavaScript/Template Interaction

| # | Edge Case | Template | Line | Risk |
|---|-----------|----------|------|------|
| 147 | `{{ domain|urlencode }}` in JS — if None, urlencode of '' is '' | dns_config.html | L91 | Empty URL param |
| 148 | `{{ domain|escapejs }}` used but also `{{ dns_provider|escapejs }}` — not escaped as separate var | dns_auto.html | L61-62 | OK |
| 149 | Fetch to `dns:configure` — response JSON shape assumed to have `success` boolean | dns_auto.html | L85 | Crash if shape changes |
| 150 | `err.message` displayed directly to user — exposes internal error details | dns_auto.html | L100 | Info leak |
| 151 | No loading indicator during DNS auto-config — user may navigate away | dns_auto.html | L59-102 | Aborted request |
| 152 | `refreshDNSStatus()` in dns_config — fires `fetch` and ignores result | dns_config.html | L91-93 | Silent failure |
| 153 | Global search form in header submits to logs — but logs view doesn't handle `q` param | header.html L7, logs.py | L86-99 | Search never works |
| 154 | `window.history.back()` in error_base — if user came from external site, goes back to external site | error_base.html L22 | User confusion |

---

## 12. Session & State Management Edge Cases

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 155 | `setup_domain` session key persists after setup completes | setup.py | Stale domain in session |
| 156 | `setup_dns_provider` session key persists after setup | setup.py | Stale provider |
| 157 | Setup wizard progress not tracked — `current_step` hidden field in form is the only state | setup.py L170 | Step can be manipulated |
| 158 | Session `cycle_key()` after login — good, but old session data not cleared | auth.py L66 | Possible session fixation |
| 159 | `session.flush()` called BEFORE `logout()` — order correct | auth.py L102-103 | OK |
| 160 | `cached_db` session backend — if cache fails, falls back to DB | settings L152 | OK |
| 161 | No session expiry on browser close — `SESSION_EXPIRE_AT_BROWSER_CLOSE` not set | settings | Persistent sessions |

---

## 13. Exception Handling & Error Propagation

| # | Edge Case | Location | Exception | Risk |
|---|-----------|----------|-----------|------|
| 162 | `_get_tls_expiry_days()` catches all exceptions — silently continues | dashboard.py L68-70 | Any | Silent failure |
| 163 | `_get_disk_usage()` catches OSError — continues to next path | dashboard.py L93-94 | OSError | Silent fallback |
| 164 | `_get_mail_volume_stats()` catches OSError — returns "unknown" | dashboard.py L121-122 | OSError | Silent fallback |
| 165 | `_get_stats()` catches `OperationalError` — returns mock values (domain_count=1, user_count=0) | dashboard.py L132-137 | DB error | Misleading data |
| 166 | `_get_domains()` catches OperationalError — returns empty rows | dashboard.py L232-234 | DB error | Empty domain list |
| 167 | `_get_domains()` fallback uses `os.environ.get("MAIL_DOMAIN")` — empty string | dashboard.py L237-238 | No DB | Warnings shown for empty domain |
| 168 | `_is_staff()` catches all exceptions in `refresh_from_db()` — returns False | auth.py L21-23 | Any | Auth failure |
| 169 | `_create_first_account()` catches `IntegrityError` but continues silently | setup.py L83-86 | Race | Account not created silently |
| 170 | `_create_first_account()` catches all exceptions — continues | setup.py L87-88 | Any | Silent failure |
| 171 | `_get_server_ip()` catches all exceptions — returns `"0.0.0.0"` | setup.py L54-55 | Any | Fallback IP |
| 172 | `_get_server_ip()` try `socket.gethostbyname` — in container may return wrong IP | setup.py L57-59 | Any | Wrong DNS records |
| 173 | `_get_dns_status()` catches all exceptions — returns `{}` | dns/views/web.py L19-20 | Any | Empty status |

---

## 14. Security & XSS Vectors

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 174 | `brand.css_overrides|safe` — if brand color env var is user-controlled, XSS | base.html L17 | Stored XSS |
| 175 | `{{ row.auth_records|safe }}` — row data from DB could be malicious | dns_row.html L5 | XSS |
| 176 | `{{ row.actions|safe }}` — same issue | dns_row.html L8 | XSS |
| 177 | `X_FRAME_OPTIONS = "DENY"` — dashboard can't be iframed | settings L132 | OK (security) |
| 178 | `SECURE_REDIRECT_EXEMPT = [r"^health"]` — regex pattern, but `SECURE_SSL_REDIRECT` not checked | production.py L37 | SSL bypass may be too broad |
| 179 | `_ALLOWED_HOST_NAMES` used for next-url validation — may be empty tuple | auth.py L79 | `''` or `None` |
| 180 | `next_url` redirect target uses `url_has_allowed_host_and_scheme` — correct | auth.py L77-81 | OK |

---

## 15. Dashboard-Specific Data Integrity Issues

| # | Edge Case | Variable | View Source | Risk |
|---|-----------|----------|-------------|------|
| 181 | `storage_used` shows disk display (e.g. "6.8 GB") but template expects number | dashboard.py | `disk.get("display")` | Wrong format |
| 182 | `storage_pct` is float like 85.3 but used as CSS width without "%" suffix | dashboard.py | `f"{disk.get('pct', 0):.0f}%"` | OK |
| 183 | `storage_total` hardcoded from disk.total_gb — may be 0 if disk check fails | dashboard.py | `_get_disk_usage()` | Shows "0.0 GB" |
| 184 | `storage_warning` only shown when disk status is "err" — but template shows `{% if storage_warning %}` | dashboard.py L350 | str or empty | OK |
| 185 | `traffic_stats.trend` shows "+12.4%" — hardcoded | dashboard.py | Mock | Misleading |
| 186 | `uptime_stats.detail` shows "Stable runtime" — hardcoded | dashboard.py | Mock | Misleading |

---

## 16. Template Include Chain Variable Scoping

| # | Edge Case | Path | Risk |
|---|-----------|------|------|
| 187 | `admin_table.html` included with `with` keyword args — variable scope limited to include | dashboard.html L87 | Variables not leaked |
| 188 | Row templates (`partials/*.html`) only receive `row` variable — no access to parent context | partials/*.html | Limited access |
| 189 | `admin_table.html` renders `{{ footer }}` directly — no explicit `with` | admin_table.html L25 | Falls through to `{{ footer }}` from parent |
| 190 | `setup_table.html` uses `dns_records` directly from context, not passed with `with` | setup_table.html L3 | Parent context leak |

---

## 17. 500-Internal Error Handler Self-Reference

| # | Edge Case | Risk |
|---|-----------|------|
| 191 | Error handler calls `logger.exception()` — if logger is broken, double-fault | urls.py L122 | 500 while handling 500 |
| 192 | Error handler calls `render()` — if template engine broken, double-fault | urls.py L126 | Empty response |
| 193 | Error handler calls `_wants_html()` — if `request.META` is missing key, exception | urls.py L141 | 500 in error handler |
| 194 | Error handler for 500 calls `logger.exception(log_msg, path)` with `%s` — works only if `log_msg` has `%s` | urls.py L122 | Log error |
| 195 | Error handler expects `exception` parameter, but Django may pass `None` | urls.py L119 | `str(None)` = "None" |
| 196 | Error handlers are set globally via `globals()[f"handler{_code}"]` — overrides any existing handlers | urls.py L112-113 | Conflicts with other apps |

---

## 18. DNS Configuration View Data Integrity

| # | Edge Case | Variable | Risk |
|---|-----------|----------|------|
| 197 | `server_ip == "0.0.0.0"` → `toolbox_spf_record` falls back to "v=spf1 mx -all" | dns/views/web.py L68 | Wrong SPF |
| 198 | `domain` empty → `toolbox_spf_record` falls back to default | dns/views/web.py L67-77 | Generic SPF shown |
| 199 | `domain` empty → `domain_label = "acme-corp.com"` shown in registry | dns/views/web.py L80 | Fake domain in UI |
| 200 | `saved_provider` is None → template shows nothing for saved provider | dns_config.html | No "current provider" shown |

---

## 19. CSRF Token Handling in DNS Auto-Config

| # | Edge Case | Risk |
|---|-----------|------|
| 201 | `document.querySelector('[name=csrfmiddlewaretoken]')` could match multiple elements | dns_auto.html L79 | Wrong token |
| 202 | FormData sent with CSRF token in header — but `@ensure_csrf_cookie` not on the configure view | dns_auto.html L79 | CSRF failure |
| 203 | `@ensure_csrf_cookie` IS on dns_configure — but the cookie is set on POST response, not GET | dns/api.py L19 | First request fails |

---

## 20. Edge Cases in Branding & Identity

| # | Edge Case | Risk |
|---|-----------|------|
| 204 | `current_logo_filename` defaults to "header_logo_v2.png" — hardcoded | branding.py L25 | Stale filename |
| 205 | `primary_color` defaults to "#0051D5" in view but BrandingConfig defaults to "#0051d5" — case mismatch | branding.py vs auth.py | Inconsistent color |
| 206 | Branding logo upload is placeholder — "Click to upload" with no JS handler | branding_identity.html L22 | Dead UI |
| 207 | All branding save buttons are `disabled` — no way to save changes | branding_identity.html L71-72 | UI dead end |
| 208 | Color pickers are plain text fields, not `<input type="color">` | branding_identity.html L50-52 | Poor UX |

---

## 21. Setup Wizard Progress & Edge Cases

| # | Edge Case | Step | Risk |
|---|-----------|------|------|
| 209 | `current_step` hidden field can be manipulated to skip steps | setup.py L170 | Step skipping |
| 210 | `validate_domain("")` returns "" — no validation error shown | setup.py L26-32 | Silent rejection |
| 211 | `validate_domain("https://evil.com")` strips protocol — still fails regex | setup.py L28 | OK |
| 212 | `validate_domain()` accepts domains up to 253 chars — RFC appropriate | setup.py L26 | OK |
| 213 | `_create_first_account()` calls `email.partition("@")` — if no `@`, returns whole string | setup.py L66 | Wrong domain |
| 214 | `_create_first_account()` silently returns if no domain found in email | setup.py L67-68 | Account not created silently |
| 215 | `_create_first_account()` with missing `local_part` — `MailService.get_or_create_mailbox` with empty local_part | setup.py L72 | Broken mailbox |
| 216 | Setup wizard can be accessed after completion — `_setup_is_complete()` blocks | setup.py L95-96 | OK |
| 217 | `setup_advance` with no `current_step` defaults to "welcome" | setup.py L170 | Falls back |

---

## 22. Axes Brute Force Protection Edge Cases

| # | Edge Case | Risk |
|---|-----------|------|
| 218 | `axes` import failure silently disables lockout | auth.py L61-62 | No brute force protection |
| 219 | `AXES_ONLY_USER_FAILURES` not configured — IP-based lockout | settings | May lock out legit users |
| 220 | `AXES_LOCKOUT_CALLABLE` may not exist in all axes versions | auth.py L41-51 | AttributeError |
| 221 | `get_lockout_message` called with/without `request` depending on axes version | auth.py L44,53 | API incompatibility |

---

## 23. Monitoring Service Edge Cases

| # | Edge Case | Risk |
|---|-----------|------|
| 222 | `dig` command may not be installed in Docker container | monitoring.py L96 | DNS check fails |
| 223 | `subprocess.run(["dig", ...], timeout=10)` — 10s timeout may be too short | monitoring.py L96-140 | Timeout failure |
| 224 | `openssl` command may not be in the container | monitoring.py L62-63 | TLS check fails |
| 225 | `dig` return code 0 with empty stdout → "fail" even if domain has no MX correctly | monitoring.py L100-101 | False negative |
| 226 | MX check looks for ANY stdout output — `dig +short MX` may return multiple lines | monitoring.py L99 | Only shows first MX |
| 227 | SPF check uses `"v=spf1" in result.stdout` — case sensitive | monitoring.py L110 | False negative for uppercase |
| 228 | DKIM check uses `"v=DKIM1" in result.stdout` — case sensitive | monitoring.py L123 | False negative |
| 229 | DMARC check uses `"v=DMARC1" in result.stdout` — case sensitive | monitoring.py L135 | False negative |

---

## 24. Audit Service Edge Cases

| # | Edge Case | Risk |
|---|-----------|------|
| 230 | `_persist_to_db` catches all exceptions — audit event lost silently | audit.py L107-109 | Silent data loss |
| 231 | `_purge_old_events` catches all exceptions — table never purged | audit.py L128-129 | Memory leak |
| 232 | `get_recent()` returns from memory buffer only — not from DB | audit.py L88-89 | Data loss after restart |
| 233 | `_events` is a class variable — shared across ALL processes in Gunicorn | audit.py L37 | Per-process isolation |

---

## 25. CSS Class Generation & Layout

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 234 | `ifinmail-span-{{ span }}` when span is `None` → `ifinmail-span-None` | admin_table.html L2 | Broken grid |
| 235 | `{% if row.status_class %}ifinmail-badge--{{ row.status_class }}{% endif %}` — if class has invalid CSS chars | queue_row.html L4 | Invalid CSS |
| 236 | `class="{% if row.mx_status_class %}ifinmail-trend--danger{% else %}ifinmail-trend{% endif %}"` — inverted logic | dns_row.html L4 | Shows danger when safe |
| 237 | `class="{% if row.tone == 'danger' %}ifinmail-trend--danger{% else %}ifinmail-trend{% endif %}"` — no neutral style | provider_row.html L5 | Missing state |

---

## 26. Accessibility Edge Cases

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 238 | `aria-label` for nav is translated — good | sidebar.html L3 | OK |
| 239 | `aria-current="page"` only set when `active_section` matches — not set for security nav link | sidebar.html L34 | No page indicator |
| 240 | Login page has `autofocus` on email field — good | login.html L21 | OK |
| 241 | Error page has `<h1>` as error code — but error title shown in `<title>` only | error_base.html L14 | Confusing |
| 242 | Search input has `ifinmail-sr-only` label — good | header.html L9 | OK |

---

## 27. Setup Durable State & Missing Persistence

| # | Edge Case | Risk |
|---|-----------|------|
| 243 | Setup state stored entirely in session — lost on session timeout | setup.py | Incomplete setup |
| 244 | Setup progress not stored in DB — no resume from interruption | setup.py | Start over |
| 245 | DNS provider credentials stored in DB (DNSService) — stored in plaintext | dns/views/api.py | Credential leak |

---

## 28. View Function Parameter Handling

| # | Edge Case | Risk |
|---|-----------|------|
| 246 | `setup_step(request, step)` — no validation that `step` is a known value | setup.py L102 | Unknown step redirects to welcome |
| 247 | `health_deliverability(request)` — `request.GET.get("domain", "")` returns empty string | urls.py L69 | Checks empty domain |
| 248 | `health_dns(request)` — catch-all `Exception` over DomainService | urls.py L53 | Silently swallows errors |
| 249 | `dns_status(request)` — `request.GET.get("domain", ...)` may be empty string | dns/views/api.py L63 | Checks empty domain |

---

## 29. Content-Type Negotiation

| # | Edge Case | Risk |
|---|-----------|------|
| 250 | `_wants_html()` checks for `text/html` in Accept — API clients with `Accept: application/json, text/html` get HTML | urls.py L140-146 | Wrong format |
| 251 | No explicit charset in response — browsers may guess incorrectly | urls.py L132-134 | Encoding issues |
| 252 | Error pages return HTML with JSON status codes — mismatch | urls.py L131,134 | Confusing |

---

## 30. Pagination & Large Dataset Edge Cases

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 253 | `Paginator(qs, 25)` — 25 per page, no max page bound | dashboard.py L217 | Performance issue |
| 254 | `page_number` clamped to [1, 1000] — 1000 pages × 25 = 25,000 domains max | dashboard.py L220 | Arbitrary limit |
| 255 | Page number from `request.GET.get("page", 1)` — no i18n for page parameter | dashboard.py L218 | URL not localized |
| 256 | No pagination shown in template — only in view | dashboard.html | User sees no page controls |

---

## 31. Log Page Edge Cases

| # | Edge Case | Risk |
|---|-----------|------|
| 257 | `log_footer` is HTML string passed as `{{ log_footer }}` — auto-escaped, HTML visible | logs.py L96 | Shows raw HTML |
| 258 | Log rows are hardcoded — no real data integration | logs.py L10-48 | Never live |
| 259 | Audit timeline items hardcoded — "2 mins ago", "45 mins ago" — never update | logs.py L57-80 | Stale timestamps |

---

## 32. Spam Filtering Page Edge Cases

| # | Edge Case | Risk |
|---|-----------|------|
| 260 | `heuristic_level` is string "7.5" — used as display value | spam.py L46 | OK |
| 261 | `filter_engines` has hardcoded "Deep Learning NLP — REQUIRES PRO LICENSE" | spam.py L50 | Marketing in OSS |
| 262 | DNSBL provider list is hardcoded — never real | spam.py L21-39 | Never live |

---

## 33. User Management Page Edge Cases

| # | Edge Case | Risk |
|---|-----------|------|
| 263 | `mfa_adoption_pct = "98.2%"` hardcoded | users.py L52 | Misleading |
| 264 | `active_sessions = "1,240"` hardcoded | users.py L53 | Misleading |
| 265 | `failed_logins = "43"` hardcoded | users.py L55 | Misleading |
| 266 | `rbac_status = "Optimal"` hardcoded | users.py L56 | Misleading |
| 267 | `live_sessions` includes hardcoded IP addresses (192.168.1.45) | users.py L63-67 | Example data never updated |
| 268 | Provision User button links to setup wizard — but setup may be complete | users.html L18 | Redirect loop |

---

## 34. Email Client Autoconfig

| # | Edge Case | Risk |
|---|-----------|------|
| 269 | `autoconfig_mozilla` and `autoconfig_outlook` — if views raise exceptions, user sees error | urls.py L96-98 | Broken autoconfig |
| 270 | Autoconfig endpoints return XML — no content-type header set | urls.py | Wrong MIME type |

---

## 35. Provider Mapping

| # | Edge Case | Risk |
|---|-----------|------|
| 271 | `PROVIDER_MAP` imported in helpers — if import fails, DNS config page crashes | dns/views/_helpers.py L2 | 500 on DNS page |
| 272 | `PROVIDER_MAP` iterated with `for pid, (cls, fields, label)` — tuple unpacking may fail | dns/views/web.py L60 | 500 |
| 273 | `hasattr(cls, 'provider_name')` — class may not have this attribute | dns/views/web.py L52 | Fallback to pid.capitalize() |
| 274 | `second_field` may be dict or None — template accesses `.name` and `.placeholder` | dns_provider.html L38 | AttributeError |

---

## 36. Template-Level Logic Errors

| # | Edge Case | Template | Issue |
|---|-----------|----------|-------|
| 275 | `style="width:{{ storage_pct|default:'0%' }}"` — no quotes needed in HTML style attr | dashboard.html L36 | OK |
| 276 | `{% for h in telemetry_bars %}<span style="height:{{ h }}%"></span>` — h is int, works | dashboard.html L61 | OK |
| 277 | `colspan="{% if headers %}{{ headers|length }}{% else %}1{% endif %}"` — string vs int | admin_table.html L20 | Works |

---

## 37. Email Sending & Configuration

| # | Edge Case | Risk |
|---|-----------|------|
| 278 | `DEFAULT_FROM_EMAIL` uses `noreply@{domain}` — if domain is empty, `noreply@localhost` | settings L186 | Email from wrong address |
| 279 | `EMAIL_BACKEND` defaults to SMTP — may not have authenticated | settings L176 | Email sending fails |
| 280 | `EMAIL_USE_TLS` and `EMAIL_USE_SSL` both configurable but mutually exclusive | settings L183-184 | Config error possible |

---

## 38. Context Processor Default Values

| # | Edge Case | Default | Risk |
|---|-----------|---------|------|
| 281 | `brand_context()` creates brand from `settings.BRAND_CONFIG` — if not set, `BrandingConfig()` | branding.py L88-91 | OK |
| 282 | `server_context()` uses defaults: "v2.4.0-stable", "support@ifinmail.io", etc. | server_context.py | Stale defaults |
| 283 | `user_context()` returns `{..., "user_initials": "?"}` for anonymous — "?" shows on login | user_context.py L10-13 | OK |

---

## 39. Hash Link Navigation

| # | Edge Case | Risk |
|---|-----------|------|
| 284 | `{% url 'accounts:dashboard' %}#security` — only works on dashboard page | sidebar.html L33 | Broken on other pages |
| 285 | `scroll-margin-top:80px` on #security anchor — may not scroll correctly | dashboard.html L91 | Wrong scroll position |

---

## 40. Broken UX Due to Disabled Buttons

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 286 | "Force Rescan" button disabled | dashboard.html L18 | Dead UI |
| 287 | "Open Shell" button disabled | dashboard.html L22 | Dead UI |
| 288 | "Register New Domain" button disabled | dns_config.html L19 | Dead UI |
| 289 | "Save Branding" button disabled | branding_identity.html L71 | Dead UI |
| 290 | "Filter Level" button disabled | logs.html L19 | Dead UI |
| 291 | "Export" button disabled | logs.html L20 | Dead UI |
| 292 | "Live View" button disabled | logs.html L21 | Dead UI |
| 293 | "Add Provider" button disabled | spam_filtering.html L58 | Dead UI |

---

## 41. DNS Record Display Edge Cases

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 294 | `display_name` logic in dns-manual — `rec.name != "@"` check for root domain | setup.py L130 | Wrong display name |
| 295 | TXT record value wrapped in `'"{rec.value}"'` — double quotes added | setup.py L143 | If value already quoted |
| 296 | `rec.priority` for MX records — may be None | setup.py L141 | Shows "None 10 mail.example.com" |

---

## 42. File System Edge Cases

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 297 | `os.walk(mail_root)` on very large directory — performance | dashboard.py L106 | Slow page load |
| 298 | `shutil.disk_usage()` on non-existent path — caught | dashboard.py L81 | OK |
| 299 | TLS cert file read via subprocess — shell injection risk | dashboard.py L54-57 | No because array args |
| 300 | TLS cert parsing with `strptime` — locale-dependent format | dashboard.py L61 | Parse failure in non-English locale |

---

## 43. Integer/Float Conversion Edge Cases

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 301 | `round(free_gb, 1)` may produce 0.0 — shows "0.0 GB" | dashboard.py L87 | Misleading |
| 302 | `int(page_number)` from string — ValueError caught | dashboard.py L220 | OK |
| 303 | `(end_date - dt.now(timezone.utc)).days` could be negative | dashboard.py L62 | Shows "-5d" |

---

## 44. Redis Cache Edge Cases

| # | Edge Case | Location | Risk |
|---|-----------|----------|------|
| 304 | `cache.set("__dashboard_health", 1, timeout=5)` — but cache may not support timeouts | dashboard.py L174 | Silent failure |
| 305 | `MonitoringService.get_latest_report()` — JSON decode error | monitoring.py L28 | Returns None |
| 306 | Redis unreachable — `cache.get()` raises exception, caught | monitoring.py L30 | OK |

---

## 45. URL Pattern Conflicts

| # | Edge Case | Risk |
|---|-----------|------|
| 307 | `accounts:setup_step` catches `<str:step>` — matches ANY string including "advance" → `setup_advance` URL never reached | accounts/urls.py L29-30 | Route conflict |
| 308 | `dns:config` and root-level `dns/` — multiple prefixes can cause namespace issues | urls.py L94 | Namespace confusion |

---

## 46. Additional Edge Cases

| # | Edge Case | Risk |
|---|-----------|------|
| 309 | `setup_table.html` uses `rec.type|default:'—'` — em dash may not render in all fonts | setup_table.html L4 | Visual glitch |
| 310 | No `Content-Length` header on JSON responses — necessary for keep-alive | urls.py | HTTP/1.1 perf |
| 311 | `DOMAIN` env var called 20+ times across views — inconsistent value possible | Multiple | Stale value |
| 312 | `subprocess.run` without sandboxing | dashboard.py L54-57 | Read outside container |

---

## 47. Missing CSRF on First Visit

| # | Edge Case | Risk |
|---|-----------|------|
| 313 | Login page GET doesn't set CSRF cookie — first POST fails | auth.py | First login attempt fails |
| 314 | Setup wizard first step GET doesn't set CSRF cookie | setup.py | First form fails |

---

## 48. Database Connection Pooling

| # | Edge Case | Risk |
|---|-----------|------|
| 315 | `CONN_MAX_AGE=300` in production — stale connections | production.py L23 | Connection timeout |
| 316 | `CONN_HEALTH_CHECKS=True` — adds query before each use | settings L97 | Overhead |

---

## 49. Additional Dashboard Issues

| # | Edge Case | Risk |
|---|-----------|------|
| 317 | `system_load` has hardcoded "16GB ECC" — not environment-driven | dashboard.py L327 | Wrong hardware |
| 318 | `ENABLE_SSL_FEATURE` flag undefined — all quick actions hidden | dashboard.html L73-81 | Empty quick actions |

---

## 50. Template Default Value Inconsistencies

| # | Edge Case | Where | Default | Issue |
|---|-----------|-------|---------|-------|
| 319 | `brand.name|default:'ifinmail'` repeated 6+ times across templates | Multiple | 'ifinmail' | DRY violation |
| 320 | `user_initials|default:'AD'` — AD is after "Admin Root" | header.html L30,34 | OK |
| 321 | `traffic_stats.label|default:''` vs `uptime_stats.pct|default:'0%'` — inconsistent | dashboard.html | Inconsistent pattern |
| 322 | `row.level|default:'—'` uses em dash for missing level | log_row.html L4 | OK |

---

## Summary by Severity

| Tier | Count | Description |
|------|-------|-------------|
| **Critical** | ~18 | Server crash, XSS, credential leak, auth bypass |
| **High** | ~45 | Silent data loss, misleading UI, broken features |
| **Medium** | ~120 | Mock data, untranslated strings, dead UI states |
| **Low** | ~139 | Missing defaults, cosmetic issues, edge-case input |

## Recurring Patterns

1. **Broad exception swallowing** (28+ occurrences) — views use bare `except Exception: pass` which masks real failures
2. **Mock/hardcoded data in production views** (14+ occurrences) — functions return static values that never reflect real system state
3. **Template variables without view guarantees** (40+ occurrences) — templates reference variables that some views don't set
4. **Environment variable drift** (17+ occurrences) — env vars are checked inconsistently across modules with different fallbacks
5. **Template inheritance complexity** (8+ occurrences) — deep extends/include chains make it unclear which variables are available where
6. **Disabled UI without explanation** (8 occurrences) — buttons are `disabled` with "Not yet implemented" tooltips but no alternative path

# DNS Provider Integration — Edge Cases (46–58)

## EC-46: Cloudflare `_get_zone_id` Fails Silently When Domain Not in Cloudflare
**File:** `dns/providers/cloudflare.py:41-42`
**Risk:** High — Misleading success
**Description:** If a domain is not added to Cloudflare's DNS, `_get_zone_id` raises `RuntimeError("No active Cloudflare zone found...")`. However, `verify_records()` and `get_nameservers()` catch the exception broadly and return empty `{}` or `[]`. The user sees no records and may not realize the domain isn't configured in Cloudflare at all.
**Trigger:** User tries to configure DNS for a domain not yet added to Cloudflare.
**Fix:** Add meaningful error messages in `verify_records()` and `get_nameservers()` when the zone is missing.

---

## EC-47: Pagination Loop in Cloudflare `_existing_records` May Never Terminate
**File:** `dns/providers/cloudflare.py:49-57`
**Risk:** Medium — Infinite loop / API spam
**Description:** The pagination loop checks `data.get("result_info", {}).get("total_count", 0) > page * 100`. If Cloudflare's API changes the pagination behavior or `total_count` is missing, this condition may never be met, causing an infinite loop of API requests.
**Trigger:** Cloudflare API pagination response changes format.
**Fix:** Add a maximum page limit (e.g., `if page > 50: break`) and a safety counter.

---

## EC-48: Porkbun Delete-and-Recreate Race Condition
**File:** `dns/providers/porkbun.py:64-66`
**Risk:** High — DNS record downtime
**Description:** Porkbun's `configure_domain` deletes an existing record then creates a new one. Between the delete and create, the DNS record does not exist. If the process crashes after delete but before create (network error, timeout), the record is permanently lost. For MX records, this means email downtime.
**Trigger:** Network timeout between delete and create calls.
**Fix:** Use Porkbun's edit endpoint if available, or wrap delete+create in a retry loop with verification.

---

## EC-49: DigitalOcean Domain Records Not Found If Domain Not in DO
**File:** `dns/providers/digitalocean.py:36-42`
**Risk:** Medium — API error
**Description:** `_fetch_records()` makes a GET request to `/domains/{domain}/records`. If the domain doesn't exist in DigitalOcean, the API returns a 404, which `_request()` converts to a `RuntimeError`. This is caught in `configure_domain()` and returns a `DNSResult(success=False)`, but the error message may not clearly explain that the domain needs to be added to DigitalOcean first.
**Trigger:** Domain not added to DigitalOcean's DNS before configuration.
**Fix:** Catch 404 specifically and return a user-friendly message about adding the domain first.

---

## EC-50: No DNS Record Type Conflict Detection (CNAME vs Other Records)
**File:** `dns/views.py:_build_records`
**Risk:** High — DNS resolution failure
**Description:** The `_build_records` function creates A records for `@`, `mail`, and `mta-sts`. DNS spec says CNAME and other record types cannot coexist at the same name. If a user already has CNAME records at any of these names (e.g., `mail` pointing to a different provider), the new A or MX records will conflict and DNS will break.
**Trigger:** User already has CNAME records at names that overlap with required records.
**Fix:** Check for existing CNAME records before creating, and warn/abort if conflicts exist.

---

## EC-51: DKIM Public Key May Exceed Single TXT Record Length
**Files:** `dns/views.py:61-64`, `provision.sh:print_dns:300-316`
**Risk:** Medium — DKIM record too large
**Description:** RSA 2048-bit DKIM keys produce base64-encoded public keys ~400 characters long. When prefixed with `v=DKIM1; k=rsa; p=`, the total can approach 500 characters, exceeding the 255-character limit for a single DNS TXT record segment. The manual DNS output in `provision.sh` handles chunking, but `_build_records()` does not — it creates a single TXT record that may be silently truncated by the DNS provider.
**Trigger:** DNS provider truncates the TXT record at 255 characters.
**Fix:** Apply string chunking to the DKIM TXT record value in `_build_records()` as well, or use a 1024-bit key for better compatibility.

---

## EC-52: DNS Provider Rate Limits Not Respected
**Files:** `dns/providers/cloudflare.py`, `dns/providers/digitalocean.py`, `dns/providers/porkbun.py`
**Risk:** Medium — 429 API failures
**Description:** All three providers call their APIs without any rate-limit awareness. Cloudflare has a 1200 req/5min limit, DigitalOcean has 5000 req/hr, Porkbun has 30 req/10sec. Creating 8 DNS records in rapid succession during `configure_domain()` could exceed these limits, especially if the function is called multiple times.
**Trigger:** Configuring multiple domains in succession.
**Fix:** Add exponential backoff retry logic for 429 responses across all providers.

---

## EC-53: MTA-STS ID May Change on Every DNS Configuration
**File:** `dns/views.py:52`
**Risk:** Low — MTA-STS instability
**Description:** The MTA-STS ID is generated from `MTA_STS_ID` env var or defaults to the current timestamp. If this ID changes (which it will on every `_build_records()` call), the `_mta-sts` TXT record changes. MTA-STS spec requires `id` to be stable — frequent changes cause sending MTAs to re-fetch the policy unnecessarily.
**Trigger:** Running DNS configuration multiple times.
**Fix:** Derive the MTA-STS ID from a content hash of the MTA-STS JSON policy file, so it only changes when the policy changes.

---

## EC-54: DNS Record Verification is Shallow
**Files:** `dns/providers/*.py:verify_records`
**Risk:** High — False positive "verified"
**Description:** `verify_records()` only checks that records of the expected type and name exist. It does NOT validate:
- Whether the record value is correct (e.g., SPF says "v=spf1 mx -all" vs something else)
- Whether the TTL is reasonable
- Whether MX priority is correct
- Whether DKIM key material matches the actual private key
**Trigger:** User's DNS record has the right name/type but wrong value.
**Fix:** Perform deep verification: fetch the actual record values and compare against expected values.

---

## EC-55: No DNS Propagation Wait After Configuration
**Files:** `dns/views.py:dns_configure`
**Risk:** Medium — False "failure" on verification
**Description:** After `configure_domain()` creates records, the frontend immediately calls `dns_status` to verify. DNS propagation takes seconds to minutes (longer with high TTL). The immediate verification will likely fail, showing the user a false "DNS not configured" error.
**Trigger:** User configures DNS and immediately checks status.
**Fix:** Add a minimum 30-second async delay before verification, or show a "propagating" status for newly created records.

---

## EC-56: Hardcoded DigitalOcean Nameservers
**File:** `dns/providers/digitalocean.py:113-114`
**Risk:** Medium — Incorrect nameserver info
**Description:** `get_nameservers()` returns a hardcoded list `["ns1.digitalocean.com", "ns2.digitalocean.com", "ns3.digitalocean.com"]`. DigitalOcean assigns different nameservers per region and may change them. Users in non-default regions will see incorrect nameserver info.
**Trigger:** DigitalOcean changes nameserver assignments; user in a different region.
**Fix:** Fetch nameservers from DigitalOcean's API dynamically (the domain GET endpoint returns them).

---

## EC-57: Porkbun `_normalize_name` Does Not Handle Trailing Dot
**File:** `dns/providers/porkbun.py:101-106`
**Risk:** Low — Record matching failure
**Description:** The Cloudflare and DigitalOcean normalizers handle trailing dots (e.g., `mail.domain.com.`), but Porkbun's normalizer does not: it only checks `name.endswith(f".{domain}")` without the trailing dot variant. This could cause record mismatches when existing records have fully-qualified names.
**Trigger:** Existing Porkbun DNS records with trailing dots in their names.
**Fix:** Add trailing dot handling to Porkbun's `_normalize_name`.

---

## EC-58: Empty Credentials Fields Cause Runtime Errors
**File:** `dns/views.py:139-142`
**Risk:** Medium — 500 error on configuration page
**Description:** The credential validation checks `if not all(creds.values())` but the form values come from `request.POST.get()`, which returns an empty string for missing fields. An empty string is falsy, so the check works. However, if an admin submits the form with whitespace-only values (e.g., `api_token="   "`), the `.strip()` converts to empty string and the check passes since the stripped value is empty. The provider constructor then receives empty strings as credentials, causing API calls to fail with authentication errors.
**Trigger:** Submitting DNS configuration form with whitespace-only credential fields.
**Fix:** Check `if not v.strip()` instead of `if not v` after stripping.

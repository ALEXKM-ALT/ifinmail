"""Cloudflare DNS provider — API v4."""
import logging
import time

import requests

from .base import DNSRecord, DNSResult

logger = logging.getLogger("backend")

CF_API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareProvider:
    provider_name = "cloudflare"

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{CF_API_BASE}{path}"
        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                resp = self.session.request(method, url, timeout=15, **kwargs)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success"):
                    errors = data.get("errors", [])
                    msg = "; ".join(e.get("message", "unknown") for e in errors)
                    raise RuntimeError(f"Cloudflare API error: {msg}")
                return data
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429 and attempt < max_retries:
                    backoff = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "Cloudflare rate limited (429), retrying in %ds (attempt %d/%d)",
                        backoff, attempt + 1, max_retries,
                    )
                    time.sleep(backoff)
                    continue
                raise RuntimeError(f"Cloudflare API request failed: {e}") from e
            except requests.RequestException as e:
                raise RuntimeError(f"Cloudflare API request failed: {e}") from e

    def _get_zone_id(self, domain: str) -> str:
        data = self._request("GET", "/zones", params={"name": domain, "status": "active"})
        zones = data.get("result", [])
        if not zones:
            raise RuntimeError(f"No active Cloudflare zone found for {domain}. Add the domain to Cloudflare first.")
        return zones[0]["id"]

    def _existing_records(self, zone_id: str, domain: str) -> dict[tuple[str, str], str]:
        """Fetch existing DNS records. Returns {(type, name): record_id}."""
        existing = {}
        page = 1
        while True:
            data = self._request("GET", f"/zones/{zone_id}/dns_records", params={"page": page, "per_page": 100})
            for rec in data.get("result", []):
                key = (rec["type"], self._normalize_name(rec["name"], domain))
                existing[key] = rec["id"]
            if not data.get("result_info", {}).get("total_count", 0) > page * 100:
                break
            page += 1
            if page > 50:
                break
        return existing

    def _normalize_name(self, name: str, domain: str) -> str:
        """Normalize record name relative to the domain. '@' → root, 'mail.domain.' → 'mail'."""
        if name == domain or name == f"{domain}." or name == "@":
            return "@"
        if name.endswith(f".{domain}") or name.endswith(f".{domain}."):
            return name[:-(len(domain) + 1)]
        return name

    def _record_payload(self, rec: DNSRecord, domain: str) -> dict:
        name = rec.name if rec.name != "@" else domain
        payload = {
            "type": rec.type,
            "name": name,
            "content": rec.value,
            "ttl": rec.ttl,
        }
        if rec.type == "MX":
            payload["priority"] = rec.priority
        return payload

    def configure_domain(self, domain: str, records: list[DNSRecord]) -> DNSResult:
        try:
            zone_id = self._get_zone_id(domain)
            existing = self._existing_records(zone_id, domain)
        except Exception as e:
            return DNSResult(success=False, message=str(e))

        created = []
        failed = []

        for rec in records:
            key = (rec.type, rec.name)
            try:
                payload = self._record_payload(rec, domain)
                if key in existing:
                    # Update existing record
                    self._request("PUT", f"/zones/{zone_id}/dns_records/{existing[key]}", json=payload)
                    logger.info("Cloudflare: updated %s %s record", domain, rec.type)
                else:
                    self._request("POST", f"/zones/{zone_id}/dns_records", json=payload)
                    logger.info("Cloudflare: created %s %s record", domain, rec.type)
                created.append(f"{rec.type} {rec.name}")
            except Exception as e:
                logger.exception("Cloudflare: failed to configure %s %s", domain, rec.type)
                failed.append(f"{rec.type} {rec.name}: {e}")

        return DNSResult(
            success=len(failed) == 0,
            message=f"Created/updated {len(created)} records" + (f", {len(failed)} failed" if failed else ""),
            records_created=created,
            records_failed=failed,
        )

    def verify_records(self, domain: str) -> dict[str, bool]:
        try:
            zone_id = self._get_zone_id(domain)
            records = self._existing_records(zone_id, domain)
        except Exception:
            return {}

        return {
            "mx": ("MX", "@") in records,
            "spf": any(k[0] == "TXT" and k[1] == "@" for k in records),
            "dkim": any(k[0] == "TXT" and k[1] == "default._domainkey" for k in records),
            "dmarc": any(k[0] == "TXT" and k[1] == "_dmarc" for k in records),
        }

    def get_nameservers(self, domain: str) -> list[str]:
        try:
            zone_id = self._get_zone_id(domain)
            data = self._request("GET", f"/zones/{zone_id}", params={})
            return data.get("result", {}).get("name_servers", [])
        except Exception:
            return []

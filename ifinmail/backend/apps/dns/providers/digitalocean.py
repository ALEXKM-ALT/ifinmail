"""DigitalOcean DNS provider."""
import logging

import requests

from .base import DNSRecord, DNSResult

logger = logging.getLogger("backend")

DO_API = "https://api.digitalocean.com/v2"


class DigitalOceanProvider:
    provider_name = "digitalocean"

    def __init__(self, api_token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{DO_API}{path}"
        try:
            resp = self.session.request(method, url, timeout=15, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"DigitalOcean API request failed: {e}") from e

    def _fetch_records(self, domain: str) -> list[dict]:
        records = []
        page = 1
        while True:
            data = self._request("GET", f"/domains/{domain}/records", params={"page": page, "per_page": 100})
            records.extend(data.get("domain_records", []))
            if data.get("links", {}).get("pages", {}).get("next"):
                page += 1
            else:
                break
        return records

    def configure_domain(self, domain: str, records: list[DNSRecord]) -> DNSResult:
        try:
            existing = self._fetch_records(domain)
        except Exception as e:
            return DNSResult(success=False, message=str(e))

        existing_map: dict[tuple[str, str], dict] = {}
        for r in existing:
            key = (r["type"], self._normalize_name(r.get("name", ""), domain))
            existing_map[key] = r

        created = []
        failed = []

        for rec in records:
            key = (rec.type, rec.name)
            try:
                payload = self._record_payload(rec, domain)
                if key in existing_map:
                    self._request("PUT", f"/domains/{domain}/records/{existing_map[key]['id']}", json=payload)
                    created.append(f"{rec.type} {rec.name} (updated)")
                else:
                    self._request("POST", f"/domains/{domain}/records", json=payload)
                    created.append(f"{rec.type} {rec.name}")
                logger.info("DO: configured %s %s record", domain, rec.type)
            except Exception as e:
                logger.exception("DO: failed to configure %s %s", domain, rec.type)
                failed.append(f"{rec.type} {rec.name}: {e}")

        return DNSResult(
            success=len(failed) == 0,
            message=f"Created/updated {len(created)} records" + (f", {len(failed)} failed" if failed else ""),
            records_created=created,
            records_failed=failed,
        )

    def _record_payload(self, rec: DNSRecord, domain: str) -> dict:
        payload: dict[str, object] = {
            "type": rec.type,
            "name": rec.name if rec.name != "@" else "@",
            "data": rec.value,
            "ttl": rec.ttl,
        }
        if rec.type == "MX":
            payload["priority"] = rec.priority
        return payload

    def _normalize_name(self, name: str, domain: str) -> str:
        if not name or name == "@" or name == domain:
            return "@"
        if name.endswith(f".{domain}") or name.endswith(f".{domain}."):
            stripped = name[:-(len(domain) + 1)]
            return stripped if stripped else "@"
        return name

    def verify_records(self, domain: str) -> dict[str, bool]:
        try:
            records = self._fetch_records(domain)
        except Exception:
            return {}

        rec_types = {(r["type"], self._normalize_name(r.get("name", ""), domain)) for r in records}
        return {
            "mx": ("MX", "@") in rec_types,
            "spf": any(t == "TXT" and n == "@" for t, n in rec_types),
            "dkim": any(t == "TXT" and "._domainkey" in n for t, n in rec_types),
            "dmarc": any(t == "TXT" and n == "_dmarc" for t, n in rec_types),
        }

    def get_nameservers(self, domain: str) -> list[str]:
        return ["ns1.digitalocean.com", "ns2.digitalocean.com", "ns3.digitalocean.com"]

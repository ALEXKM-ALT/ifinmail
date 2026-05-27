"""Porkbun DNS provider."""
import json
import logging
import time

import requests

from .base import DNSRecord, DNSResult

logger = logging.getLogger("backend")

PORKBUN_API = "https://api.porkbun.com/api/json/v3"


class PorkbunProvider:
    provider_name = "porkbun"

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.session = requests.Session()

    def _request(self, path: str, body: dict | None = None) -> dict:
        payload = {
            "apikey": self.api_key,
            "secretapikey": self.secret_key,
        }
        if body:
            payload.update(body)

        try:
            resp = self.session.post(f"{PORKBUN_API}{path}", json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "SUCCESS":
                raise RuntimeError(f"Porkbun API error: {data.get('message', 'unknown')}")
            return data
        except requests.RequestException as e:
            raise RuntimeError(f"Porkbun API request failed: {e}") from e

    def _fetch_records(self, domain: str) -> list[dict]:
        data = self._request(f"/dns/retrieve/{domain}")
        return data.get("records", [])

    def configure_domain(self, domain: str, records: list[DNSRecord]) -> DNSResult:
        try:
            existing = self._fetch_records(domain)
        except Exception as e:
            return DNSResult(success=False, message=str(e))

        # Build lookup: (type, name) → record dict
        existing_map: dict[tuple[str, str], dict] = {}
        for r in existing:
            key = (r["type"], self._normalize_name(r.get("name", ""), domain))
            existing_map[key] = r

        created = []
        failed = []

        for rec in records:
            key = (rec.type, rec.name)
            try:
                body = self._record_body(rec, domain)
                if key in existing_map:
                    # Delete and recreate (Porkbun edit API has different format)
                    self._request(f"/dns/delete/{domain}/{existing_map[key]['id']}")
                    for retry in range(3):
                        try:
                            self._request(f"/dns/create/{domain}", body)
                            break
                        except Exception:
                            if retry < 2:
                                logger.warning(
                                    "Porkbun: create after delete failed for %s %s, retrying (attempt %d/3)",
                                    domain, rec.type, retry + 2,
                                )
                                time.sleep(1)
                            else:
                                raise
                    logger.info("Porkbun: updated %s %s record", domain, rec.type)
                else:
                    self._request(f"/dns/create/{domain}", body)
                    logger.info("Porkbun: created %s %s record", domain, rec.type)
                created.append(f"{rec.type} {rec.name}")
            except Exception as e:
                logger.exception("Porkbun: failed to configure %s %s", domain, rec.type)
                failed.append(f"{rec.type} {rec.name}: {e}")

        return DNSResult(
            success=len(failed) == 0,
            message=f"Created/updated {len(created)} records" + (f", {len(failed)} failed" if failed else ""),
            records_created=created,
            records_failed=failed,
        )

    def _record_body(self, rec: DNSRecord, domain: str) -> dict:
        body: dict[str, object] = {
            "type": rec.type,
            "content": rec.value,
            "ttl": str(rec.ttl),
        }
        if rec.name == "@":
            body["name"] = ""
        elif rec.name.endswith("._domainkey"):
            body["name"] = rec.name
        elif rec.name.startswith("_"):
            body["name"] = rec.name
        else:
            body["name"] = rec.name
        if rec.type == "MX":
            body["prio"] = str(rec.priority)
        return body

    def _normalize_name(self, name: str, domain: str) -> str:
        if not name or name == domain:
            return "@"
        if name.endswith(f".{domain}") or name.endswith(f".{domain}."):
            return name[:-(len(domain) + 1)]
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
        try:
            data = self._request(f"/domain/getNs/{domain}")
            return data.get("ns", [])
        except Exception:
            return []

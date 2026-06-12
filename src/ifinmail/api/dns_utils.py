"""DNS lookup utilities for domain verification."""

import logging

import dns.exception
import dns.resolver

logger = logging.getLogger("ifinmail.dns_utils")


def resolve_txt(name: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(name, "TXT", lifetime=10)
        return ["".join(s.decode() if isinstance(s, bytes) else s for s in r.strings) for r in answers]
    except dns.resolver.NXDOMAIN:
        return []
    except dns.resolver.NoAnswer:
        return []
    except dns.exception.Timeout:
        logger.warning("DNS timeout for TXT %s", name)
        return []
    except Exception as e:
        logger.warning("DNS error for TXT %s: %s", name, e)
        return []


def resolve_mx(domain: str) -> list[tuple[int, str]]:
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=10)
        return [(r.preference, str(r.exchange).rstrip(".")) for r in answers]
    except dns.resolver.NXDOMAIN:
        return []
    except dns.resolver.NoAnswer:
        return []
    except dns.exception.Timeout:
        logger.warning("DNS timeout for MX %s", domain)
        return []
    except Exception as e:
        logger.warning("DNS error for MX %s: %s", domain, e)
        return []


def check_spf(domain: str) -> dict:
    records = resolve_txt(domain)
    for rec in records:
        if rec.strip().startswith("v=spf1"):
            return {"ok": True, "value": rec}
    return {"ok": False, "value": None}


def check_dkim(domain: str) -> dict:
    records = resolve_txt(f"default._domainkey.{domain}")
    for rec in records:
        if "v=DKIM1" in rec:
            return {"ok": True, "value": rec}
    if records:
        return {"ok": True, "value": records[0]}
    return {"ok": False, "value": None}


def check_dmarc(domain: str) -> dict:
    records = resolve_txt(f"_dmarc.{domain}")
    for rec in records:
        if rec.strip().startswith("v=DMARC1"):
            return {"ok": True, "value": rec}
    return {"ok": False, "value": None}


def check_mx(domain: str) -> dict:
    records = resolve_mx(domain)
    return {"ok": len(records) > 0, "records": [(pref, ex) for pref, ex in records]}


def check_verification_token(domain: str, token: str) -> dict:
    records = resolve_txt(f"_verify.{domain}")
    for rec in records:
        if token in rec:
            return {"ok": True, "value": rec}
    return {"ok": False, "value": None}

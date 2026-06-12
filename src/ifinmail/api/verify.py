import logging
import re

import dns.resolver
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ifinmail.api.auth import get_current_user
from ifinmail.db.models import User

logger = logging.getLogger("ifinmail.verify")

router = APIRouter(prefix="/verify-email", tags=["verify"])

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "temp-mail.org", "throwaway.email",
    "10minutemail.com", "yopmail.com", "trashmail.com", "sharklasers.com",
    "mail.tm", "tempmail.com", "tempemail.com", "fakeinbox.com",
    "mailnesia.com", "getairmail.com", "minutemail.com", "spamgourmet.com",
    "maildrop.cc", "dispostable.com", "mailcatch.com", "emailondeck.com",
    "inboxbear.com", "burnermail.io", "moakt.com", "tempinbox.com",
}

PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class VerifyRequest(BaseModel):
    email: str


class VerifyResponse(BaseModel):
    valid: bool
    mx: bool
    disposable: bool
    risk: str
    suggestions: list[str] = []


def _get_mx_records(domain: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=10)
        return [str(r.exchange) for r in answers]
    except Exception:
        return []


def _suggestions(email: str) -> list[str]:
    common = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "protonmail.com"}
    _, domain = email.split("@", 1)
    if domain not in common:
        for known in common:
            if domain[:2] == known[:2]:
                return [f"{email.split('@')[0]}@{known}"]
    return []


@router.post("", response_model=VerifyResponse)
def verify_email(
    req: VerifyRequest,
    user: User = Depends(get_current_user),
):
    email = req.email.strip().lower()
    if not PATTERN.match(email):
        return VerifyResponse(valid=False, mx=False, disposable=False, risk="invalid", suggestions=[])

    _, domain = email.split("@", 1)
    disposable = domain in DISPOSABLE_DOMAINS
    mx_records = _get_mx_records(domain)
    has_mx = len(mx_records) > 0

    if not has_mx:
        risk = "high"
    elif disposable:
        risk = "high"
    else:
        risk = "low"

    return VerifyResponse(
        valid=has_mx,
        mx=has_mx,
        disposable=disposable,
        risk=risk,
        suggestions=_suggestions(email) if not has_mx else [],
    )

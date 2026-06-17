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
    "mailinator.com",
    "guerrillamail.com",
    "temp-mail.org",
    "throwaway.email",
    "10minutemail.com",
    "yopmail.com",
    "trashmail.com",
    "sharklasers.com",
    "mail.tm",
    "tempmail.com",
    "tempemail.com",
    "fakeinbox.com",
    "mailnesia.com",
    "getairmail.com",
    "minutemail.com",
    "spamgourmet.com",
    "maildrop.cc",
    "dispostable.com",
    "mailcatch.com",
    "emailondeck.com",
    "inboxbear.com",
    "burnermail.io",
    "moakt.com",
    "tempinbox.com",
    "emailfake.com",
    "mailnator.com",
    "tempmail.net",
    "mailmetrash.com",
    "spambox.com",
    "mailexpire.com",
    "throwaway.de",
    "spambob.com",
    "spamcorptastic.com",
    "nowmymail.com",
    "mailinator2.com",
    "sogetthis.com",
    "mailsac.com",
    "mytemp.email",
    "mail-temp.com",
    "emailtemporal.com",
    "mailet.com",
    "oneoffemail.com",
    "mailforspam.com",
    "spamspot.com",
    "sneakemail.com",
    "jetable.org",
    "kasmail.com",
    "mt2009.com",
    "mt2014.com",
    "mt2015.com",
    "filzmail.com",
    "thankyou2010.com",
    "trash2009.com",
    "mt2008.com",
    "msgos.com",
    "podam.pl",
    "wupics.com",
    "shortmail.net",
    "spam.la",
    "spamherelots.com",
    "spamhereplease.com",
    "spamthisplease.com",
    "thisisnotmyrealemail.com",
    "trashymail.com",
    "whatiaas.com",
    "whyspam.me",
    "youmails.org",
    "temp-mail.ru",
    "mintemail.com",
    "tyldd.com",
    "discard.email",
    "discardmail.com",
    "discardmail.de",
    "spamo.com",
    "spamgoat.com",
    "spamex.com",
    "spamlot.com",
    "spamspamspam.com",
    "trashymail.net",
    "mytempemail.com",
    "emailtempmail.com",
}

ROLE_PREFIXES = {
    "admin",
    "administrator",
    "info",
    "support",
    "contact",
    "sales",
    "noreply",
    "no-reply",
    "postmaster",
    "hostmaster",
    "webmaster",
    "abuse",
    "root",
    "mailer-daemon",
    "mailerdaemon",
}

COMMON_PROVIDERS = {
    "gmail.com": "gmail.com",
    "yahoo.com": "yahoo.com",
    "outlook.com": "outlook.com",
    "hotmail.com": "hotmail.com",
    "icloud.com": "icloud.com",
    "protonmail.com": "protonmail.com",
    "aol.com": "aol.com",
    "mail.com": "mail.com",
    "zoho.com": "zoho.com",
    "yandex.com": "yandex.com",
    "gmx.com": "gmx.com",
}

DOMAIN_TYPOS = {
    "gamil.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gmil.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gmaill.com": "gmail.com",
    "yaho.com": "yahoo.com",
    "yahooo.com": "yahoo.com",
    "yahho.com": "yahoo.com",
    "hotmai.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
    "hotmil.com": "hotmail.com",
    "outlok.com": "outlook.com",
    "outllok.com": "outlook.com",
    "outloo.com": "outlook.com",
    "protomail.com": "protonmail.com",
    "protonail.com": "protonmail.com",
    "icoud.com": "icloud.com",
    "icould.com": "icloud.com",
}

# RFC 5321 / 5322 compliant pattern (simplified)
LOCAL_PATTERN = re.compile(r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+$")
PATTERN = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$"
)


def validate_email_syntax(email: str) -> str | None:
    """Returns an error message if invalid, None if syntax is OK."""
    if not email or "@" not in email:
        return "Missing @ symbol"
    local, at, domain = email.partition("@")
    if not local or len(local) > 64:
        return "Local part must be 1-64 characters"
    if not domain or len(domain) > 255:
        return "Domain part must be 1-255 characters"
    if ".." in local:
        return "Consecutive dots not allowed in local part"
    if local.startswith(".") or local.endswith("."):
        return "Local part cannot start or end with a dot"
    if not LOCAL_PATTERN.match(local):
        return "Local part contains invalid characters"
    if not PATTERN.match(email):
        return "Email does not match valid format"
    return None


class VerifyRequest(BaseModel):
    email: str


class VerifyResponse(BaseModel):
    valid: bool
    syntax_valid: bool = True
    syntax_error: str | None = None
    mx: bool
    disposable: bool
    role_based: bool
    risk: str
    suggestions: list[str] = []


def _get_mx_records(domain: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=10)
        return [str(r.exchange) for r in answers]
    except Exception:
        return []


def _suggestions(email: str) -> list[str]:
    _, domain = email.split("@", 1)

    # Check for known typos
    if domain in DOMAIN_TYPOS:
        return [f"{email.split('@')[0]}@{DOMAIN_TYPOS[domain]}"]

    # Check for common providers with similar first 2 chars
    for known_domain in COMMON_PROVIDERS:
        if domain[:2] == known_domain[:2] and domain != known_domain:
            return [f"{email.split('@')[0]}@{known_domain}"]

    return []


@router.post("", response_model=VerifyResponse)
def verify_email(
    req: VerifyRequest,
    user: User = Depends(get_current_user),
):
    email = req.email.strip().lower()

    syntax_error = validate_email_syntax(email)
    if syntax_error:
        return VerifyResponse(
            valid=False,
            syntax_valid=False,
            syntax_error=syntax_error,
            mx=False,
            disposable=False,
            role_based=False,
            risk="invalid",
            suggestions=[],
        )

    local, domain = email.split("@", 1)
    disposable = domain in DISPOSABLE_DOMAINS
    role_based = local in ROLE_PREFIXES
    mx_records = _get_mx_records(domain)
    has_mx = len(mx_records) > 0

    if not has_mx:
        risk = "high"
    elif disposable:
        risk = "high"
    elif role_based:
        risk = "medium"
    else:
        risk = "low"

    return VerifyResponse(
        valid=has_mx,
        syntax_valid=True,
        mx=has_mx,
        disposable=disposable,
        role_based=role_based,
        risk=risk,
        suggestions=_suggestions(email),
    )

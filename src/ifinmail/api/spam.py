import logging
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ifinmail.api.auth import get_current_user
from ifinmail.db.models import User

logger = logging.getLogger("ifinmail.spam")

router = APIRouter(prefix="/spam-check", tags=["spam"])

SPAM_TRIGGERS = {
    "free", "win", "winner", "congratulations", "click here", "act now",
    "limited time", "urgent", "guaranteed", "exclusive offer", "buy now",
    "subscribe", "cash", "bonus", "earn money", "work from home",
    "no cost", "risk free", "100%", "amazing", "call now", "order now",
    "don't delete", "this is not spam", "great offer", "special promotion",
    "double your", "extra income", "financial freedom", "opt in",
    "unlimited", "while supplies last", " Best price", "deal",
    "discount", "save big", "fantastic", "incredible", "gift",
    "prize", "guarantee", "million", "billion", "bargain",
}


class SpamCheckRequest(BaseModel):
    subject: str = ""
    body_text: str = ""
    body_html: str | None = None
    from_addr: str = ""
    to_addr: str = ""


class SpamCheckResponse(BaseModel):
    score: int
    risk: str
    flags: list[str]


@router.post("", response_model=SpamCheckResponse)
def spam_check(
    req: SpamCheckRequest,
    user: User = Depends(get_current_user),
):
    text = f"{req.subject} {req.body_text} {req.body_html or ''}".lower()
    flags = []
    score = 0

    for trigger in SPAM_TRIGGERS:
        if trigger.lower() in text:
            flags.append(f"spam_word:{trigger}")
            score += 10

    all_caps_words = [w for w in re.findall(r"\b[A-Z]{4,}\b", req.subject)]
    if all_caps_words:
        flags.append(f"all_caps:{','.join(all_caps_words[:3])}")
        score += 15

    exclamation_count = req.subject.count("!")
    if exclamation_count >= 3:
        flags.append(f"excessive_exclamation:{exclamation_count}")
        score += 10

    if req.subject and req.subject[0].islower():
        flags.append("subject_lowercase_start")
        score += 5

    if req.body_text and len(req.body_text) < 20:
        flags.append("very_short_body")
        score += 5

    if req.body_html and req.body_text and len(req.body_text) < len(req.body_html) * 0.1:
        flags.append("text_html_ratio")
        score += 10

    if score >= 50:
        risk = "high"
    elif score >= 20:
        risk = "medium"
    else:
        risk = "low"

    return SpamCheckResponse(score=min(score, 100), risk=risk, flags=flags)

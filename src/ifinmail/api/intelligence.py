import logging
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ifinmail.api.auth import get_current_user
from ifinmail.db.models import User

logger = logging.getLogger("ifinmail.intelligence")

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

POSITIVE_WORDS = {"great", "excellent", "amazing", "fantastic", "wonderful", "good", "happy", "love", "best", "thank", "thanks", "pleased", "delighted", "perfect", "awesome"}
NEGATIVE_WORDS = {"bad", "terrible", "awful", "horrible", "poor", "worst", "hate", "angry", "upset", "disappointed", "frustrated", "sorry", "apologize", "complaint", "issue", "problem", "error", "failed", "broken"}

LANG_PATTERNS = {
    "english": r"\b(the|is|are|was|were|have|has|been|will|would|could|should|this|that|with|from|your|our|their)\b",
    "swahili": r"\b(na|ya|wa|kwa|katika|kutoka|kwenye|hii|hizi|wako|wetu|yako|yenu)\b",
    "french": r"\b(le|la|les|des|est|sont|ont|avec|dans|pour|sur|cette|ces|votre|notre|leurs)\b",
    "arabic": r"[\u0600-\u06FF]",
}


class IntelligenceRequest(BaseModel):
    email: str = ""
    subject: str = ""
    body_text: str = ""
    body_html: str | None = None


class IntelligenceResponse(BaseModel):
    spam_probability: str
    business_score: str
    sentiment: str
    language: str
    summary: str
    word_count: int


@router.post("/analyze", response_model=IntelligenceResponse)
def analyze(
    req: IntelligenceRequest,
    user: User = Depends(get_current_user),
):
    text = f"{req.subject} {req.body_text} {req.body_html or ''}"
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    word_count = len(words)

    spam_score = _calc_spam(text, words)

    sentiment = _calc_sentiment(words)

    language = _detect_language(text)

    business_score = _calc_business_score(text, req.email, word_count)

    summary = _generate_summary(req.subject, req.body_text or req.body_html or "", word_count)

    return IntelligenceResponse(
        spam_probability=f"{spam_score}%",
        business_score=f"{business_score}%",
        sentiment=sentiment,
        language=language,
        summary=summary,
        word_count=word_count,
    )


def _calc_spam(text: str, words: list[str]) -> int:
    spam_triggers = {"free", "win", "winner", "click here", "act now", "limited time", "urgent", "guaranteed", "exclusive offer", "buy now", "cash", "bonus", "congratulations", "risk free", "100%"}
    text_lower = text.lower()
    score = 0
    for t in spam_triggers:
        if t in text_lower:
            score += 8
    if len(words) < 5:
        score += 15
    exclaim = text.count("!")
    if exclaim >= 3:
        score += 10
    caps = sum(1 for w in re.findall(r"\b[A-Z]{4,}\b", text))
    score += caps * 5
    return min(score, 98)


def _calc_sentiment(words: list[str]) -> str:
    word_set = set(words)
    pos = len(word_set & POSITIVE_WORDS)
    neg = len(word_set & NEGATIVE_WORDS)
    if pos > neg + 1:
        return "positive"
    if neg > pos + 1:
        return "negative"
    return "neutral"


def _detect_language(text: str) -> str:
    scores = {}
    for lang, pattern in LANG_PATTERNS.items():
        matches = len(re.findall(pattern, text.lower()))
        if lang == "arabic":
            matches = len(re.findall(pattern, text))
        scores[lang] = matches
    if max(scores.values()) == 0:
        return "unknown"
    return max(scores, key=scores.get)


def _calc_business_score(text: str, email: str, word_count: int) -> int:
    biz_words = {"meeting", "proposal", "invoice", "contract", "project", "deadline", "budget", "report", "client", "partner", "revenue", "growth", "strategy", "team", "schedule", "deliverable", "agenda"}
    word_set = set(text.lower().split())
    biz_hits = len(word_set & biz_words)
    score = 30 + biz_hits * 5
    if word_count > 20:
        score += 10
    if email and "@" in email:
        domain = email.split("@")[1]
        if domain not in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com"):
            score += 10
    return min(score, 99)


def _generate_summary(subject: str, body: str, word_count: int) -> str:
    if not subject and not body:
        return "Empty email"
    if subject:
        s = subject.strip()
        if word_count > 50:
            return f"Email about '{s}' with {word_count} words"
        return f"Email about '{s}'"
    first_words = " ".join(body.split()[:15])
    if len(first_words) > 50:
        first_words = first_words[:50] + "..."
    return f"Email starting with: {first_words}"

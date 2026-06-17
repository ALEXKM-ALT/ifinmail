import json
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ifinmail.api.auth import get_current_user
from ifinmail.api.config import settings
from ifinmail.db.models import User

logger = logging.getLogger("ifinmail.ai")

router = APIRouter(prefix="/ai", tags=["ai"])

PROMPT_GENERATE = """You are an expert email writer. Write a professional email
based on the user's request. Keep it concise and clear.

User request: {prompt}

Additional context:
- Subject: {subject}
- Tone: {tone}
- Recipient: {to}

Output the email as JSON with "subject" and "body" keys. Body should be plain text."""

PROMPT_REPLY = """Write a reply email to the following email.
Match the tone of the original.

Original email:
{original_email}

Additional context:
- Key points to address: {key_points}
- Tone: {tone}

Output the reply as JSON with "body" as the only key. Keep it concise."""

PROMPT_SUMMARIZE = """Summarize the following email in 2-3 sentences.
Capture the key points, action items, and any deadlines mentioned.

Email subject: {subject}
Email body: {body}

Output the summary as JSON with "summary" as the only key."""

PROMPT_TRANSLATE = """Translate the following email text from {source_lang}
to {target_lang}. Preserve the tone and formality of the original.

Text to translate:
{text}

Output the translation as JSON with "translated_text" as the only key."""


class GenerateRequest(BaseModel):
    prompt: str
    subject: str = ""
    tone: str = "professional"
    to: str = ""


class ReplyRequest(BaseModel):
    original_email: str
    key_points: str = ""
    tone: str = "professional"


class SummarizeRequest(BaseModel):
    subject: str = ""
    body: str


class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "auto"
    target_lang: str


class AIResponse(BaseModel):
    result: dict


class AIConfigResponse(BaseModel):
    configured: bool
    provider: str = ""


def _call_openai(prompt: str) -> dict:
    api_key = settings.openai_api_key or ""
    model = settings.openai_model or "gpt-4o-mini"

    if not api_key:
        return _fallback_local_response(prompt)

    try:
        import httpx

        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 1024,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("\n", 1)[0]
        return json.loads(content)
    except Exception as e:
        logger.warning("OpenAI call failed, using fallback: %s", e)
        return _fallback_local_response(prompt)


def _fallback_local_response(prompt: str) -> dict:
    if "Translate" in prompt:
        return {"translated_text": "[Translation would appear here — set OPENAI_API_KEY to enable AI translation]"}
    if "Summarize" in prompt:
        return {"summary": "[Summary would appear here — set OPENAI_API_KEY to enable AI summarization]"}
    if "Write a reply" in prompt:
        return {"body": "[Reply would appear here — set OPENAI_API_KEY to enable AI replies]"}
    return {
        "subject": "[Subject would appear here]",
        "body": (
            "[Email body would appear here. Set OPENAI_API_KEY in environment to enable AI-powered email generation.]"
        ),
    }


@router.get("/config", response_model=AIConfigResponse)
def ai_config(
    user: User = Depends(get_current_user),
):
    return AIConfigResponse(
        configured=bool(settings.openai_api_key),
        provider="openai" if settings.openai_api_key else "fallback",
    )


@router.post("/generate", response_model=AIResponse)
def ai_generate(
    req: GenerateRequest,
    user: User = Depends(get_current_user),
):
    prompt = PROMPT_GENERATE.format(prompt=req.prompt, subject=req.subject, tone=req.tone, to=req.to)
    result = _call_openai(prompt)
    return AIResponse(result=result)


@router.post("/reply", response_model=AIResponse)
def ai_reply(
    req: ReplyRequest,
    user: User = Depends(get_current_user),
):
    prompt = PROMPT_REPLY.format(original_email=req.original_email, key_points=req.key_points, tone=req.tone)
    result = _call_openai(prompt)
    return AIResponse(result=result)


@router.post("/summarize", response_model=AIResponse)
def ai_summarize(
    req: SummarizeRequest,
    user: User = Depends(get_current_user),
):
    prompt = PROMPT_SUMMARIZE.format(subject=req.subject, body=req.body)
    result = _call_openai(prompt)
    return AIResponse(result=result)


@router.post("/translate", response_model=AIResponse)
def ai_translate(
    req: TranslateRequest,
    user: User = Depends(get_current_user),
):
    prompt = PROMPT_TRANSLATE.format(text=req.text, source_lang=req.source_lang, target_lang=req.target_lang)
    result = _call_openai(prompt)
    return AIResponse(result=result)

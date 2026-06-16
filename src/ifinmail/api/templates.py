import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.config import settings
from ifinmail.api.deps import get_db
from ifinmail.api.mail import _relay_send
from ifinmail.db.models import EmailTemplate, User

logger = logging.getLogger("ifinmail.templates")

router = APIRouter(prefix="/templates", tags=["templates"])

VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


class TemplateCreate(BaseModel):
    name: str
    subject: str
    body_html: str | None = None
    body_text: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None


class TemplateRender(BaseModel):
    template_id: int
    variables: dict[str, str]


class TemplateTestSend(BaseModel):
    template_id: int
    to: str
    variables: dict[str, str] = {}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_template(
    req: TemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    variables = sorted(set(VARIABLE_PATTERN.findall(req.subject) + VARIABLE_PATTERN.findall(req.body_html or "") + VARIABLE_PATTERN.findall(req.body_text or "")))
    template = EmailTemplate(
        user_id=user.id,
        name=req.name,
        subject=req.subject,
        body_html=req.body_html,
        body_text=req.body_text,
        variables=json.dumps(variables),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return {
        "id": template.id,
        "name": template.name,
        "subject": template.subject,
        "variables": variables,
    }


@router.get("")
def list_templates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    templates = db.query(EmailTemplate).filter(EmailTemplate.user_id == user.id).order_by(EmailTemplate.name).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "subject": t.subject,
            "variables": json.loads(t.variables) if t.variables else [],
            "created_at": t.created_at.isoformat() if t.created_at else "",
        }
        for t in templates
    ]


@router.get("/{template_id}")
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id, EmailTemplate.user_id == user.id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return {
        "id": template.id,
        "name": template.name,
        "subject": template.subject,
        "body_html": template.body_html,
        "body_text": template.body_text,
        "variables": json.loads(template.variables) if template.variables else [],
        "created_at": template.created_at.isoformat() if template.created_at else "",
        "updated_at": template.updated_at.isoformat() if template.updated_at else "",
    }


@router.put("/{template_id}")
def update_template(
    template_id: int,
    req: TemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id, EmailTemplate.user_id == user.id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if req.name is not None:
        template.name = req.name
    if req.subject is not None:
        template.subject = req.subject
    if req.body_html is not None:
        template.body_html = req.body_html
    if req.body_text is not None:
        template.body_text = req.body_text
    subject = req.subject if req.subject is not None else template.subject
    body_html = req.body_html if req.body_html is not None else template.body_html
    body_text = req.body_text if req.body_text is not None else template.body_text
    variables = sorted(set(VARIABLE_PATTERN.findall(subject) + VARIABLE_PATTERN.findall(body_html or "") + VARIABLE_PATTERN.findall(body_text or "")))
    template.variables = json.dumps(variables)
    db.commit()
    db.refresh(template)
    return {
        "id": template.id,
        "name": template.name,
        "subject": template.subject,
        "variables": variables,
    }


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id, EmailTemplate.user_id == user.id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    db.delete(template)
    db.commit()


@router.post("/render")
def render_template(
    req: TemplateRender,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.id == req.template_id, EmailTemplate.user_id == user.id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    def _replace(text: str) -> str:
        if not text:
            return ""
        return VARIABLE_PATTERN.sub(lambda m: req.variables.get(m.group(1), m.group(0)), text)
    return {
        "subject": _replace(template.subject),
        "body_html": _replace(template.body_html or ""),
        "body_text": _replace(template.body_text or ""),
    }


@router.post("/test-send")
def test_send_template(
    req: TemplateTestSend,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.id == req.template_id, EmailTemplate.user_id == user.id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if not settings.smtp_host:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="SMTP relay not configured")

    def _replace(text: str) -> str:
        if not text:
            return ""
        return VARIABLE_PATTERN.sub(lambda m: req.variables.get(m.group(1), m.group(0)), text)

    subject = _replace(template.subject)
    body_text = _replace(template.body_text or "")
    body_html = _replace(template.body_html or "")

    _relay_send(user.email, req.to, subject, body_text, body_html or None)

    return {"message": "Test email sent", "to": req.to, "subject": subject}

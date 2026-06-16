import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.api.limiter import user_moderate
from ifinmail.db.models import Campaign, CampaignStep, ScheduledMessage, User

logger = logging.getLogger("ifinmail.scheduler_api")

router = APIRouter(prefix="/mail", tags=["mail_scheduler"])


# ── Pydantic schemas ──

class ScheduleRequest(BaseModel):
    to_addr: str
    subject: str = ""
    body_text: str = ""
    body_html: str | None = None
    cc_addr: str | None = None
    bcc_addr: str | None = None
    attachment_ids: list[int] | None = None
    scheduled_at: datetime
    repeat_interval: str | None = None
    repeat_until: datetime | None = None

    @field_validator("repeat_interval")
    @classmethod
    def validate_repeat(cls, v: str | None) -> str | None:
        if v is not None and v not in ("daily", "weekly", "monthly"):
            raise ValueError("repeat_interval must be daily, weekly, or monthly")
        return v


class ScheduleResponse(BaseModel):
    id: int
    to_addr: str
    subject: str
    scheduled_at: datetime
    repeat_interval: str | None = None
    repeat_until: datetime | None = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleUpdateRequest(BaseModel):
    to_addr: str | None = None
    subject: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    cc_addr: str | None = None
    bcc_addr: str | None = None
    attachment_ids: list[int] | None = None
    scheduled_at: datetime | None = None
    repeat_interval: str | None = None
    repeat_until: datetime | None = None


# ── Campaign schemas ──

class CampaignCreate(BaseModel):
    name: str
    description: str = ""


class CampaignOut(BaseModel):
    id: int
    name: str
    description: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    steps: list["CampaignStepOut"] = []

    model_config = ConfigDict(from_attributes=True)


class CampaignStepCreate(BaseModel):
    order: int = 0
    delay_days: int = 0
    subject: str = ""
    body_text: str = ""
    body_html: str | None = None


class CampaignStepOut(BaseModel):
    id: int
    campaign_id: int
    order: int
    delay_days: int
    subject: str
    body_text: str
    body_html: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CampaignLaunch(BaseModel):
    recipients: list[str]


# ── Standalone scheduling ──

@router.post("/schedule", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def schedule_email(
    req: ScheduleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = user_moderate,
):
    if req.scheduled_at <= datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scheduled_at must be in the future")
    sm = ScheduledMessage(
        user_id=user.id,
        to_addr=req.to_addr,
        cc_addr=req.cc_addr,
        bcc_addr=req.bcc_addr,
        subject=req.subject,
        body_text=req.body_text,
        body_html=req.body_html,
        attachment_ids=json.dumps(req.attachment_ids) if req.attachment_ids else None,
        scheduled_at=req.scheduled_at,
        repeat_interval=req.repeat_interval,
        repeat_until=req.repeat_until,
    )
    db.add(sm)
    db.commit()
    db.refresh(sm)
    return ScheduleResponse(
        id=sm.id,
        to_addr=sm.to_addr,
        subject=sm.subject,
        scheduled_at=sm.scheduled_at,
        repeat_interval=sm.repeat_interval,
        repeat_until=sm.repeat_until,
        status=sm.status,
        created_at=sm.created_at,
    )


@router.get("/scheduled", response_model=list[ScheduleResponse])
def list_scheduled(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(ScheduledMessage).filter(ScheduledMessage.user_id == user.id)
    if status_filter:
        query = query.filter(ScheduledMessage.status == status_filter)
    query = query.order_by(ScheduledMessage.scheduled_at.asc())
    return [
        ScheduleResponse(
            id=sm.id,
            to_addr=sm.to_addr,
            subject=sm.subject,
            scheduled_at=sm.scheduled_at,
            repeat_interval=sm.repeat_interval,
            repeat_until=sm.repeat_until,
            status=sm.status,
            created_at=sm.created_at,
        )
        for sm in query.all()
    ]


@router.get("/scheduled/{message_id}", response_model=ScheduleResponse)
def get_scheduled(message_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sm = db.query(ScheduledMessage).filter(ScheduledMessage.id == message_id, ScheduledMessage.user_id == user.id).first()
    if not sm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled message not found")
    return ScheduleResponse(
        id=sm.id,
        to_addr=sm.to_addr,
        subject=sm.subject,
        scheduled_at=sm.scheduled_at,
        repeat_interval=sm.repeat_interval,
        repeat_until=sm.repeat_until,
        status=sm.status,
        created_at=sm.created_at,
    )


@router.put("/scheduled/{message_id}", response_model=ScheduleResponse)
def update_scheduled(
    message_id: int,
    req: ScheduleUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = user_moderate,
):
    sm = db.query(ScheduledMessage).filter(ScheduledMessage.id == message_id, ScheduledMessage.user_id == user.id).first()
    if not sm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled message not found")
    if sm.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending messages can be updated")
    if req.to_addr is not None:
        sm.to_addr = req.to_addr
    if req.subject is not None:
        sm.subject = req.subject
    if req.body_text is not None:
        sm.body_text = req.body_text
    if req.body_html is not None:
        sm.body_html = req.body_html
    if req.cc_addr is not None:
        sm.cc_addr = req.cc_addr
    if req.bcc_addr is not None:
        sm.bcc_addr = req.bcc_addr
    if req.attachment_ids is not None:
        sm.attachment_ids = json.dumps(req.attachment_ids)
    if req.scheduled_at is not None:
        if req.scheduled_at <= datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scheduled_at must be in the future")
        sm.scheduled_at = req.scheduled_at
    if req.repeat_interval is not None:
        if req.repeat_interval not in ("daily", "weekly", "monthly"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="repeat_interval must be daily, weekly, or monthly")
        sm.repeat_interval = req.repeat_interval
    if req.repeat_until is not None:
        sm.repeat_until = req.repeat_until
    db.commit()
    db.refresh(sm)
    return ScheduleResponse(
        id=sm.id,
        to_addr=sm.to_addr,
        subject=sm.subject,
        scheduled_at=sm.scheduled_at,
        repeat_interval=sm.repeat_interval,
        repeat_until=sm.repeat_until,
        status=sm.status,
        created_at=sm.created_at,
    )


@router.delete("/scheduled/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_scheduled(message_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sm = db.query(ScheduledMessage).filter(ScheduledMessage.id == message_id, ScheduledMessage.user_id == user.id).first()
    if not sm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled message not found")
    db.delete(sm)
    db.commit()


# ── Campaigns ──

@router.post("/campaigns", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    req: CampaignCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    campaign = Campaign(name=req.name, description=req.description, created_by=user.id)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return CampaignOut(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        created_by=campaign.created_by,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        steps=[],
    )


@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaigns = db.query(Campaign).filter(Campaign.created_by == user.id).order_by(Campaign.created_at.desc()).all()
    result = []
    for c in campaigns:
        steps = [
            CampaignStepOut(
                id=s.id,
                campaign_id=s.campaign_id,
                order=s.order,
                delay_days=s.delay_days,
                subject=s.subject,
                body_text=s.body_text,
                body_html=s.body_html,
            )
            for s in c.steps
        ]
        result.append(CampaignOut(
            id=c.id,
            name=c.name,
            description=c.description,
            created_by=c.created_by,
            created_at=c.created_at,
            updated_at=c.updated_at,
            steps=steps,
        ))
    return result


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.created_by == user.id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    steps = [
        CampaignStepOut(
            id=s.id,
            campaign_id=s.campaign_id,
            order=s.order,
            delay_days=s.delay_days,
            subject=s.subject,
            body_text=s.body_text,
            body_html=s.body_html,
        )
        for s in c.steps
    ]
    return CampaignOut(
        id=c.id,
        name=c.name,
        description=c.description,
        created_by=c.created_by,
        created_at=c.created_at,
        updated_at=c.updated_at,
        steps=steps,
    )


@router.put("/campaigns/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: int,
    req: CampaignCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.created_by == user.id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    c.name = req.name
    c.description = req.description
    db.commit()
    db.refresh(c)
    steps = [
        CampaignStepOut(
            id=s.id,
            campaign_id=s.campaign_id,
            order=s.order,
            delay_days=s.delay_days,
            subject=s.subject,
            body_text=s.body_text,
            body_html=s.body_html,
        )
        for s in c.steps
    ]
    return CampaignOut(
        id=c.id,
        name=c.name,
        description=c.description,
        created_by=c.created_by,
        created_at=c.created_at,
        updated_at=c.updated_at,
        steps=steps,
    )


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.created_by == user.id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    db.delete(c)
    db.commit()


# ── Campaign steps ──

@router.post("/campaigns/{campaign_id}/steps", response_model=CampaignStepOut, status_code=status.HTTP_201_CREATED)
def add_campaign_step(
    campaign_id: int,
    req: CampaignStepCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.created_by == user.id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    step = CampaignStep(
        campaign_id=c.id,
        order=req.order,
        delay_days=req.delay_days,
        subject=req.subject,
        body_text=req.body_text,
        body_html=req.body_html,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return CampaignStepOut(
        id=step.id,
        campaign_id=step.campaign_id,
        order=step.order,
        delay_days=step.delay_days,
        subject=step.subject,
        body_text=step.body_text,
        body_html=step.body_html,
    )


@router.put("/campaigns/steps/{step_id}", response_model=CampaignStepOut)
def update_campaign_step(
    step_id: int,
    req: CampaignStepCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    step = (
        db.query(CampaignStep)
        .join(Campaign)
        .filter(CampaignStep.id == step_id, Campaign.created_by == user.id)
        .first()
    )
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    step.order = req.order
    step.delay_days = req.delay_days
    step.subject = req.subject
    step.body_text = req.body_text
    step.body_html = req.body_html
    db.commit()
    db.refresh(step)
    return CampaignStepOut(
        id=step.id,
        campaign_id=step.campaign_id,
        order=step.order,
        delay_days=step.delay_days,
        subject=step.subject,
        body_text=step.body_text,
        body_html=step.body_html,
    )


@router.delete("/campaigns/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign_step(step_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    step = (
        db.query(CampaignStep)
        .join(Campaign)
        .filter(CampaignStep.id == step_id, Campaign.created_by == user.id)
        .first()
    )
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    db.delete(step)
    db.commit()


# ── Launch campaign ──

@router.post("/campaigns/{campaign_id}/launch", status_code=status.HTTP_200_OK)
def launch_campaign(
    campaign_id: int,
    req: CampaignLaunch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = user_moderate,
):
    c = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.created_by == user.id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    steps = db.query(CampaignStep).filter(CampaignStep.campaign_id == c.id).order_by(CampaignStep.order).all()
    if not steps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign has no steps")
    if not req.recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No recipients specified")

    from datetime import timedelta

    now = datetime.utcnow()
    count = 0
    for recipient in req.recipients:
        cumulative_delay = 0
        for step in steps:
            cumulative_delay += step.delay_days
            sm = ScheduledMessage(
                user_id=user.id,
                campaign_id=c.id,
                campaign_step_id=step.id,
                to_addr=recipient.strip(),
                subject=step.subject,
                body_text=step.body_text,
                body_html=step.body_html,
                scheduled_at=now + timedelta(days=cumulative_delay),
            )
            db.add(sm)
            count += 1
    db.commit()
    return {"launched": True, "recipients": len(req.recipients), "steps": len(steps), "scheduled": count}

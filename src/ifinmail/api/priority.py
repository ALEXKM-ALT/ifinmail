import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from ifinmail.db.models import Contact, Message

_URGENT_WORDS = re.compile(
    r"\b(urgent|important|asap|deadline|action required|immediate|"
    r"time sensitive|critical|priority|review|approval|invoice|"
    r"meeting|confirmation|reminder|follow.up|response needed)\b",
    re.IGNORECASE,
)


def score_message(msg: Message, db: Session) -> float:
    score = 0.0

    mailbox_id = msg.mailbox_id

    sender_email = msg.from_addr.lower().strip()

    contact = (
        db.query(Contact)
        .filter(Contact.user_id == _user_id_for_mailbox(mailbox_id, db), Contact.email == sender_email)
        .first()
    )
    if contact:
        score += 3.0

    sent_count = (
        db.query(func.count(Message.id))
        .filter(
            Message.mailbox_id == mailbox_id,
            Message.folder == "SENT",
            Message.to_addrs.ilike(f"%{sender_email}%"),
        )
        .scalar()
        or 0
    )
    if sent_count > 0:
        score += min(sent_count * 1.0, 3.0)

    same_domain = _user_domain_for_mailbox(mailbox_id, db)
    if same_domain and sender_email.endswith("@" + same_domain):
        score += 2.0

    if msg.has_attachments:
        score += 1.0

    if msg.subject:
        matches = _URGENT_WORDS.findall(msg.subject)
        if matches:
            score += min(len(matches) * 1.5, 3.0)

    if sent_count == 0:
        score -= 1.0

    return max(score, -5.0)


def _user_id_for_mailbox(mailbox_id: int, db: Session) -> int:
    from ifinmail.db.models import Mailbox
    mb = db.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
    return mb.user_id if mb else 0


def _user_domain_for_mailbox(mailbox_id: int, db: Session) -> str | None:
    from ifinmail.db.models import Mailbox
    mb = db.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
    if mb and "@" in mb.email:
        return mb.email.split("@")[1]
    return None

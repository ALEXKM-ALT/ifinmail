import logging

from sqlalchemy.orm import Session

from ifinmail.db.models import AuditLog, User

logger = logging.getLogger("ifinmail.audit")


def log_admin_action(
    db: Session,
    admin: User,
    action: str,
    target_user: str | None = None,
    target_email: str | None = None,
    details: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    log = AuditLog(
        admin_id=admin.id,
        action=action,
        target_user=target_user,
        target_email=target_email,
        details=details,
        ip_address=ip_address,
    )
    db.add(log)
    db.flush()
    logger.info("Audit: %s by %s%s", action, admin.email, f" on {target_user}" if target_user else "")
    return log

import json
import logging
import re

from sqlalchemy.orm import Session

from ifinmail.db.models import CustomFolder, FilterRule, Mailbox, Message

logger = logging.getLogger("ifinmail.filters")

CONDITION_FIELDS = {"from_addr", "to_addr", "subject", "body_text"}

OPERATOR_MAP: dict[str, callable] = {
    "contains": lambda f, v: v in f,
    "not_contains": lambda f, v: v not in f,
    "equals": lambda f, v: f == v,
    "not_equals": lambda f, v: f != v,
    "starts_with": lambda f, v: f.startswith(v),
    "ends_with": lambda f, v: f.endswith(v),
    "regex": lambda f, v: bool(re.search(v, f)),
}


def _eval_condition(cond: dict, ctx: dict[str, str]) -> bool:
    field = cond.get("field", "")
    operator = cond.get("operator", "")
    value = str(cond.get("value", "")).lower()
    raw = ctx.get(field, "")
    if not raw:
        return False
    fn = OPERATOR_MAP.get(operator)
    if not fn:
        return False
    return fn(raw.lower(), value)


def _condition_matches(rule: FilterRule, ctx: dict[str, str]) -> bool:
    conditions = json.loads(rule.conditions) if isinstance(rule.conditions, str) else rule.conditions
    if not conditions:
        return False
    if rule.match_logic == "any":
        return any(_eval_condition(c, ctx) for c in conditions)
    return all(_eval_condition(c, ctx) for c in conditions)


def _apply_actions(rule: FilterRule, msg: Message, mailbox: Mailbox, db: Session):
    actions = json.loads(rule.actions) if isinstance(rule.actions, str) else rule.actions
    for act in actions:
        atype = act.get("type", "")
        avalue = str(act.get("value", ""))
        if atype == "move_to_folder":
            folder = avalue.upper()
            valid_std = {"INBOX", "SENT", "DRAFTS", "TRASH", "SPAM", "ARCHIVE"}
            if folder in valid_std:
                msg.folder = folder
            else:
                custom = (
                    db.query(CustomFolder)
                    .filter(CustomFolder.mailbox_id == mailbox.id, CustomFolder.name == folder)
                    .first()
                )
                if custom:
                    msg.folder = folder
        elif atype == "mark_read":
            msg.read = 1 if avalue != "0" else 0
        elif atype == "mark_starred":
            msg.starred = 1 if avalue != "0" else 0
        elif atype == "add_label":
            existing = (msg.labels or "").strip()
            labels = [l.strip() for l in existing.split(",") if l.strip()]
            if avalue and avalue not in labels:
                labels.append(avalue)
                msg.labels = ",".join(labels)
        elif atype == "discard":
            msg.folder = "TRASH"
        elif atype == "delete":
            msg.folder = "TRASH"
        # forward_to is handled by the caller if needed


def apply_filters_for_mailbox(
    db: Session,
    mailbox: Mailbox,
    recipient: str,
    ctx: dict[str, str],
    msg: Message,
):
    """Evaluate all enabled filter rules for a mailbox and modify msg in place."""
    rules = (
        db.query(FilterRule)
        .filter(FilterRule.mailbox_id == mailbox.id, FilterRule.enabled == 1)
        .order_by(FilterRule.order.asc())
        .all()
    )
    if not rules:
        return
    env = dict(ctx)
    env["to_addr"] = recipient
    for rule in rules:
        if _condition_matches(rule, env):
            logger.info("Filter '%s' matched message from %s to %s", rule.name, ctx.get("from_addr"), recipient)
            _apply_actions(rule, msg, mailbox, db)
            # If discarded, no need to check further rules
            if msg.folder == "TRASH":
                break

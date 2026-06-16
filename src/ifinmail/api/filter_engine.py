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


def _apply_actions(rule: FilterRule, msg: Message, mailbox: Mailbox, db: Session, ctx: dict | None = None):
    actions = json.loads(rule.actions) if isinstance(rule.actions, str) else rule.actions
    stop_after = False
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
        elif atype == "stop":
            stop_after = True
        elif atype == "forward":
            _action_forward(avalue, ctx, mailbox, db)
        elif atype == "auto_reply":
            _action_auto_reply(avalue, ctx, mailbox, db)
        elif atype == "notify":
            _action_notify(avalue, ctx, mailbox)
    if stop_after:
        msg.folder = "TRASH"


def _action_forward(target: str, ctx: dict | None, mailbox: Mailbox, db: Session):
    if not ctx or not target or "@" not in target:
        return
    try:
        from ifinmail.api.mail import _relay_send
        _relay_send(
            from_addr=mailbox.email,
            to_addr=target,
            subject=ctx.get("subject", "(forwarded)"),
            body_text=ctx.get("body_text", ""),
            body_html=ctx.get("body_html") or None,
        )
    except Exception as exc:
        logger.warning("Filter forward failed: %s", exc)


def _action_auto_reply(template_body: str, ctx: dict | None, mailbox: Mailbox, db: Session):
    if not ctx or not template_body:
        return
    try:
        original_from = ctx.get("from_addr", "")
        original_subject = ctx.get("subject", "")
        if not original_from or "@" not in original_from:
            return
        from ifinmail.db.models import Message
        reply = Message(
            mailbox_id=mailbox.id,
            from_addr=mailbox.email,
            to_addrs=original_from,
            subject=f"Re: {original_subject}" if original_subject else "Re:",
            body_text=template_body,
            folder="SENT",
        )
        db.add(reply)
        db.flush()
        from ifinmail.api.mail import _relay_send
        _relay_send(
            from_addr=mailbox.email,
            to_addr=original_from,
            subject=reply.subject,
            body_text=template_body,
        )
        logger.info("Filter auto-reply sent to %s from %s", original_from, mailbox.email)
    except Exception as exc:
        logger.warning("Filter auto-reply failed: %s", exc)


def _action_notify(webhook_url: str, ctx: dict | None, mailbox: Mailbox):
    if not ctx or not webhook_url or not webhook_url.startswith("http"):
        return
    try:
        import urllib.request
        import json as _json
        payload = _json.dumps({
            "event": "filter_matched",
            "mailbox": mailbox.email,
            "from": ctx.get("from_addr", ""),
            "to": ctx.get("to_addr", ""),
            "subject": ctx.get("subject", ""),
        }).encode()
        req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        logger.warning("Filter notify failed: %s", exc)


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
            _apply_actions(rule, msg, mailbox, db, env)
            if msg.folder == "TRASH":
                break

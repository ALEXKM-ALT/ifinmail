from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Domain(Base):
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(255), nullable=False, unique=True, index=True)
    verified = Column(Integer, nullable=False, server_default=text("0"))
    verification_token = Column(String(64), nullable=True)
    spf_ok = Column(Integer, nullable=False, server_default=text("0"))
    dkim_ok = Column(Integer, nullable=False, server_default=text("0"))
    dkim_private_key = Column(Text, nullable=True)
    dkim_selector = Column(String(64), nullable=True)
    dmarc_ok = Column(Integer, nullable=False, server_default=text("0"))
    mx_ok = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="domain", cascade="all, delete-orphan")
    aliases = relationship("Alias", back_populates="domain", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password = Column(Text, nullable=False)
    domain_id = Column(Integer, ForeignKey("domains.id", ondelete="CASCADE"), nullable=False)
    is_admin = Column(Integer, nullable=False, server_default=text("0"))
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    last_login = Column(DateTime, nullable=True)
    storage_limit = Column(BigInteger, nullable=False, server_default=text("0"))
    quota_warning_sent = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    domain = relationship("Domain", back_populates="users")
    mailbox = relationship("Mailbox", uselist=False, back_populates="user", cascade="all, delete-orphan")


class Mailbox(Base):
    __tablename__ = "mailboxes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quota_mb = Column(Integer, nullable=False, server_default=text("1024"))
    used_mb = Column(Integer, nullable=False, server_default=text("0"))
    enabled = Column(Integer, nullable=False, server_default=text("1"))
    plan = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="mailbox")
    messages = relationship("Message", back_populates="mailbox", cascade="all, delete-orphan")


class Alias(Base):
    __tablename__ = "aliases"
    __table_args__ = (
        UniqueConstraint("source", "target", name="uq_alias_source_target"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255), nullable=False, index=True)
    target = Column(String(255), nullable=False)
    domain_id = Column(Integer, ForeignKey("domains.id", ondelete="CASCADE"), nullable=False)
    enabled = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    domain = relationship("Domain", back_populates="aliases")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(String(255), nullable=True, index=True)
    from_addr = Column(String(255), nullable=False)
    to_addrs = Column(Text, nullable=False)
    cc_addrs = Column(Text, nullable=True)
    bcc_addrs = Column(Text, nullable=True)
    subject = Column(String(512), nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    size = Column(Integer, nullable=False, server_default=text("0"))
    read = Column(Integer, nullable=False, server_default=text("0"))
    starred = Column(Integer, nullable=False, server_default=text("0"))
    has_attachments = Column(Integer, nullable=False, server_default=text("0"))
    folder = Column(String(32), nullable=False, server_default=text("'INBOX'"))
    in_reply_to = Column(String(255), nullable=True)
    references = Column(Text, nullable=True)
    labels = Column(Text, nullable=True)
    previous_folder = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    mailbox = relationship("Mailbox")
    attachments = relationship("Attachment", back_populates="message", cascade="all, delete-orphan")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(255), nullable=False, server_default=text("'application/octet-stream'"))
    size = Column(Integer, nullable=False, server_default=text("0"))
    storage_path = Column(String(512), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    message = relationship("Message", back_populates="attachments")


class VacationResponder(Base):
    __tablename__ = "vacation_responders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False, unique=True)
    subject = Column(String(255), nullable=False, server_default=text("'Auto-reply'"))
    body = Column(Text, nullable=False, server_default=text("''"))
    enabled = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ForwardingRule(Base):
    __tablename__ = "forwarding_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False)
    target_email = Column(String(255), nullable=False)
    enabled = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class CustomFolder(Base):
    __tablename__ = "custom_folders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    mailbox = relationship("Mailbox")


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False, index=True)
    description = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)
    subject = Column(String(512), nullable=False)
    body_html = Column(Text, nullable=True)
    body_text = Column(Text, nullable=True)
    variables = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class TwoFactor(Base):
    __tablename__ = "two_factor"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    secret = Column(String(64), nullable=False)
    enabled = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User")


class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_delivery_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    webhook_id = Column(Integer, ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False)
    event = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    response_code = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, server_default=text("0"))
    next_retry_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    webhook = relationship("Webhook")


class EmailDelivery(Base):
    __tablename__ = "email_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    recipient = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, server_default=text("'pending'"))
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    bounce_type = Column(String(64), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    message = relationship("Message")
    tracking_events = relationship("TrackingEvent", back_populates="delivery", cascade="all, delete-orphan")


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_id = Column(Integer, ForeignKey("email_deliveries.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(16), nullable=False)
    timestamp = Column(DateTime, nullable=False, server_default=func.now())
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    city = Column(String(128), nullable=True)
    region = Column(String(128), nullable=True)
    country = Column(String(128), nullable=True)
    device_type = Column(String(32), nullable=True)
    os = Column(String(64), nullable=True)
    browser = Column(String(64), nullable=True)
    clicked_url = Column(String(2048), nullable=True)

    delivery = relationship("EmailDelivery", back_populates="tracking_events")


class SSOState(Base):
    __tablename__ = "sso_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    state = Column(String(64), unique=True, nullable=False, index=True)
    provider = Column(String(32), nullable=False)
    redirect_uri = Column(String(512), nullable=False)
    code_verifier = Column(String(256), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    max_users = Column(Integer, nullable=False, server_default=text("10"))
    plan = Column(String(32), nullable=False, server_default=text("'free'"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    owner = relationship("User", foreign_keys=[owner_id])


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(32), nullable=False, server_default=text("'member'"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    organization = relationship("Organization")
    user = relationship("User", foreign_keys=[user_id])


class OrganizationInvite(Base):
    __tablename__ = "organization_invites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)
    role = Column(String(32), nullable=False, server_default=text("'member'"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    accepted = Column(Boolean, nullable=False, server_default=text("0"))

    organization = relationship("Organization")


class OrgContact(Base):
    __tablename__ = "org_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    organization = relationship("Organization")
    creator = relationship("User")


class Backup(Base):
    __tablename__ = "backups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(512), nullable=False)
    size_bytes = Column(BigInteger, nullable=False, server_default=text("0"))
    status = Column(String(32), nullable=False, server_default=text("'pending'"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(512), nullable=False)
    events = Column(Text, nullable=False)
    secret = Column(String(128), nullable=False)
    active = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)
    key_prefix = Column(String(8), nullable=False)
    key_hash = Column(String(128), nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    active = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(64), nullable=False)
    target_user = Column(String(255), nullable=True)
    target_email = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    admin = relationship("User", foreign_keys=[admin_id])


class OrgEmailAssignment(Base):
    __tablename__ = "org_email_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    organization = relationship("Organization")
    message = relationship("Message")
    assignee = relationship("User", foreign_keys=[assigned_to])
    assigner = relationship("User", foreign_keys=[assigned_by])


class OrgEmailNote(Base):
    __tablename__ = "org_email_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    organization = relationship("Organization")
    message = relationship("Message")
    user = relationship("User")


class OrgSharedInboxMessage(Base):
    __tablename__ = "org_shared_inbox_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    from_email = Column(String(255), nullable=False)
    to_email = Column(String(255), nullable=True)
    subject = Column(String(512), nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, server_default=text("'pending'"))
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    organization = relationship("Organization")
    assignee = relationship("User", foreign_keys=[assigned_to])
    assigner = relationship("User", foreign_keys=[assigned_by])
    notes = relationship("OrgSharedInboxNote", back_populates="message", cascade="all, delete-orphan")


class OrgSharedInboxNote(Base):
    __tablename__ = "org_shared_inbox_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shared_inbox_message_id = Column(Integer, ForeignKey("org_shared_inbox_messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    message = relationship("OrgSharedInboxMessage", back_populates="notes")
    user = relationship("User")


class FilterRule(Base):
    __tablename__ = "filter_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False, server_default=text("''"))
    enabled = Column(Integer, nullable=False, server_default=text("1"))
    order = Column(Integer, nullable=False, server_default=text("0"))
    match_logic = Column(String(8), nullable=False, server_default=text("'all'"))
    conditions = Column(Text, nullable=False)
    actions = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    mailbox = relationship("Mailbox")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    creator = relationship("User")
    steps = relationship("CampaignStep", back_populates="campaign", cascade="all, delete-orphan",
                         order_by="CampaignStep.order")


class CampaignStep(Base):
    __tablename__ = "campaign_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    order = Column(Integer, nullable=False, server_default=text("0"))
    delay_days = Column(Integer, nullable=False, server_default=text("0"))
    subject = Column(String(512), nullable=False, server_default=text("''"))
    body_text = Column(Text, nullable=False, server_default=text("''"))
    body_html = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    campaign = relationship("Campaign", back_populates="steps")


class ScheduledMessage(Base):
    __tablename__ = "scheduled_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    campaign_step_id = Column(Integer, ForeignKey("campaign_steps.id", ondelete="SET NULL"), nullable=True)
    to_addr = Column(String(255), nullable=False)
    cc_addr = Column(String(255), nullable=True)
    bcc_addr = Column(String(255), nullable=True)
    subject = Column(String(512), nullable=False, server_default=text("''"))
    body_text = Column(Text, nullable=False, server_default=text("''"))
    body_html = Column(Text, nullable=True)
    attachment_ids = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, server_default=text("'pending'"))
    error = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    campaign = relationship("Campaign")
    step = relationship("CampaignStep")
    sent_message = relationship("Message")


class ImapImport(Base):
    __tablename__ = "imap_imports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    host = Column(String(255), nullable=False, server_default=text("'imap.gmail.com'"))
    port = Column(Integer, nullable=False, server_default=text("993"))
    username = Column(String(255), nullable=False)
    password = Column(Text, nullable=False)
    use_ssl = Column(Integer, nullable=False, server_default=text("1"))
    folder = Column(String(64), nullable=False, server_default=text("'INBOX'"))
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(32), nullable=True)
    last_run_count = Column(Integer, nullable=True, server_default=text("0"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User")

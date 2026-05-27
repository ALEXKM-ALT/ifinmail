from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
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

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255), nullable=False, unique=True, index=True)
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

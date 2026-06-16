import email.utils
from email.message import EmailMessage
from unittest.mock import patch

import pytest
from aiosmtpd.smtp import MISSING, Envelope
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ifinmail.db.models import (
    Alias,
    Base,
    Domain,
    Mailbox,
    Message,
    Organization,
    OrganizationMember,
    User,
)
from ifinmail.smtp.handler import SMTPHandler, _decode_part, _recipient_exists, _resolve_recipients


@pytest.fixture
def db_engine():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def db_session(db_engine):
    conn = db_engine.connect()
    tx = conn.begin()
    session = sessionmaker(bind=conn)()
    yield session
    session.close()
    tx.rollback()
    conn.close()


@pytest.fixture
def domain(db_session):
    d = Domain(domain="example.com", verified=1)
    db_session.add(d)
    db_session.flush()
    return d


@pytest.fixture
def user(db_session, domain):
    u = User(email="alice@example.com", password="hash", domain_id=domain.id, is_admin=0)
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def mailbox(db_session, user):
    m = Mailbox(email="alice@example.com", user_id=user.id, plan="free")
    db_session.add(m)
    db_session.flush()
    return m


@pytest.fixture
def second_mailbox(db_session, domain):
    u = User(email="bob@example.com", password="hash", domain_id=domain.id, is_admin=0)
    db_session.add(u)
    db_session.flush()
    m = Mailbox(email="bob@example.com", user_id=u.id, plan="free")
    db_session.add(m)
    db_session.flush()
    return m


@pytest.fixture
def sample_email_bytes():
    msg = EmailMessage()
    msg["From"] = "sender@external.com"
    msg["To"] = "alice@example.com"
    msg["Subject"] = "Test message"
    msg["Message-ID"] = "<test-msg-id@example.com>"
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg.set_content("Hello Alice, this is a test.")
    return bytes(msg)


@pytest.fixture
def sample_envelope(sample_email_bytes):
    env = Envelope
    env.mail_from = "sender@external.com"
    env.rcpt_tos = ["alice@example.com"]
    env.content = sample_email_bytes
    return env


# ── _recipient_exists ──


class TestRecipientExists:
    def test_existing_mailbox(self, db_session, mailbox):
        assert _recipient_exists(db_session, "alice@example.com") is True

    def test_existing_alias(self, db_session, domain, mailbox):
        alias = Alias(source="info@example.com", target="alice@example.com", domain_id=domain.id, enabled=1)
        db_session.add(alias)
        db_session.flush()
        assert _recipient_exists(db_session, "info@example.com") is True

    def test_disabled_alias(self, db_session, domain):
        alias = Alias(source="info@example.com", target="nobody@example.com", domain_id=domain.id, enabled=0)
        db_session.add(alias)
        db_session.flush()
        assert _recipient_exists(db_session, "info@example.com") is False

    def test_existing_org(self, db_session, user):
        org = Organization(name="Test Org", email="org@example.com", owner_id=user.id)
        db_session.add(org)
        db_session.flush()
        assert _recipient_exists(db_session, "org@example.com") is True

    def test_nonexistent(self, db_session):
        assert _recipient_exists(db_session, "nobody@example.com") is False

    def test_unknown_domain(self, db_session):
        assert _recipient_exists(db_session, "x@unknown.com") is False


# ── _resolve_recipients ──


class TestResolveRecipients:
    def test_direct_mailbox(self, db_session, mailbox):
        result = _resolve_recipients(db_session, "alice@example.com")
        assert len(result) == 1
        assert result[0].email == "alice@example.com"

    def test_alias_resolves(self, db_session, domain, mailbox):
        alias = Alias(source="info@example.com", target="alice@example.com", domain_id=domain.id, enabled=1)
        db_session.add(alias)
        db_session.flush()
        result = _resolve_recipients(db_session, "info@example.com")
        assert len(result) == 1
        assert result[0].email == "alice@example.com"

    def test_org_resolves_to_members(self, db_session, domain, user, mailbox, second_mailbox):
        org = Organization(name="Test Org", email="team@example.com", owner_id=user.id)
        db_session.add(org)
        db_session.flush()
        other = db_session.query(User).filter(User.email == "bob@example.com").first()
        db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id))
        db_session.add(OrganizationMember(organization_id=org.id, user_id=other.id))
        db_session.flush()
        result = _resolve_recipients(db_session, "team@example.com")
        assert len(result) == 2
        assert {m.email for m in result} == {"alice@example.com", "bob@example.com"}

    def test_unknown_returns_empty(self, db_session):
        result = _resolve_recipients(db_session, "nobody@example.com")
        assert result == []


# ── _decode_part ──


class TestDecodePart:
    def test_decode_plain_text(self):
        from email.mime.text import MIMEText
        part = MIMEText("Hello world", _charset="utf-8")
        assert _decode_part(part) == "Hello world"

    def test_decode_invalid_charset_fallback(self):
        from email.mime.text import MIMEText
        part = MIMEText("Hello", _charset="utf-8")
        part.set_payload(b"\xff\xfe\x00", charset=None)
        result = _decode_part(part)
        assert isinstance(result, str)

    def test_decode_none_payload(self):
        msg = EmailMessage()
        msg["Content-Type"] = "text/plain"
        msg.set_payload(None)
        assert _decode_part(msg) == ""


# ── handle_RCPT ──


class TestHandleRCPT:
    @pytest.mark.anyio
    async def test_accept_known_recipient(self, db_session, mailbox):
        handler = SMTPHandler()
        with patch("ifinmail.smtp.handler.SessionLocal", return_value=db_session):
            result = await handler.handle_RCPT(None, None, None, "alice@example.com", [])
        assert result is MISSING

    @pytest.mark.anyio
    async def test_reject_unknown(self, db_session):
        handler = SMTPHandler()
        with patch("ifinmail.smtp.handler.SessionLocal", return_value=db_session):
            result = await handler.handle_RCPT(None, None, None, "unknown@example.com", [])
        assert result == "550 No such user"


# ── handle_DATA ──


class MockSession:
    """Minimal mock for aiosmtpd Session."""
    pass


class TestHandleDATA:
    @pytest.mark.anyio
    async def test_store_message(self, db_session, mailbox):
        handler = SMTPHandler()

        msg = EmailMessage()
        msg["From"] = "sender@external.com"
        msg["To"] = "alice@example.com"
        msg["Subject"] = "Hello"
        msg["Message-ID"] = "<unique@test>"
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg.set_content("Test body")

        env = Envelope
        env.mail_from = "sender@external.com"
        env.rcpt_tos = ["alice@example.com"]
        env.content = bytes(msg)

        with patch("ifinmail.smtp.handler.SessionLocal", return_value=db_session):
            result = await handler.handle_DATA(None, MockSession(), env)

        assert result is MISSING

        stored = db_session.query(Message).filter(Message.message_id == "<unique@test>").first()
        assert stored is not None
        assert stored.subject == "Hello"
        assert stored.from_addr == "sender@external.com"
        assert stored.to_addrs == "alice@example.com"
        assert stored.body_text.strip() == "Test body"
        assert stored.folder == "INBOX"

    @pytest.mark.anyio
    async def test_dedup_same_message_id(self, db_session, mailbox):
        handler = SMTPHandler()

        msg = EmailMessage()
        msg["From"] = "sender@external.com"
        msg["To"] = "alice@example.com"
        msg["Subject"] = "Dup"
        msg["Message-ID"] = "<dedup-test@test>"
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg.set_content("First")

        env = Envelope
        env.mail_from = "sender@external.com"
        env.rcpt_tos = ["alice@example.com"]
        env.content = bytes(msg)

        with patch("ifinmail.smtp.handler.SessionLocal", return_value=db_session):
            await handler.handle_DATA(None, MockSession(), env)

        count_after_first = db_session.query(Message).filter(Message.message_id == "<dedup-test@test>").count()
        assert count_after_first == 1

        with patch("ifinmail.smtp.handler.SessionLocal", return_value=db_session):
            await handler.handle_DATA(None, MockSession(), env)

        count_after_second = db_session.query(Message).filter(Message.message_id == "<dedup-test@test>").count()
        assert count_after_second == 1

    @pytest.mark.anyio
    async def test_multiple_recipients(self, db_session, mailbox, second_mailbox):
        handler = SMTPHandler()

        msg = EmailMessage()
        msg["From"] = "sender@external.com"
        msg["To"] = "alice@example.com, bob@example.com"
        msg["Subject"] = "Multi"
        msg["Message-ID"] = "<multi-test@test>"
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg.set_content("Hi both")

        env = Envelope
        env.mail_from = "sender@external.com"
        env.rcpt_tos = ["alice@example.com", "bob@example.com"]
        env.content = bytes(msg)

        with patch("ifinmail.smtp.handler.SessionLocal", return_value=db_session):
            result = await handler.handle_DATA(None, MockSession(), env)

        assert result is MISSING
        count = db_session.query(Message).filter(Message.message_id == "<multi-test@test>").count()
        assert count == 2

    @pytest.mark.anyio
    async def test_no_valid_recipients(self, db_session):
        handler = SMTPHandler()

        msg = EmailMessage()
        msg["From"] = "sender@external.com"
        msg["To"] = "nobody@example.com"
        msg["Subject"] = "Test"
        msg["Message-ID"] = "<no-rcpt@test>"
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg.set_content("Test")

        env = Envelope
        env.mail_from = "sender@external.com"
        env.rcpt_tos = ["nobody@example.com"]
        env.content = bytes(msg)

        with patch("ifinmail.smtp.handler.SessionLocal", return_value=db_session):
            result = await handler.handle_DATA(None, MockSession(), env)

        assert result == "550 No valid recipients"

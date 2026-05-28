"""User management service layer."""
import logging

from django.db.models import QuerySet
from django.db.utils import OperationalError

from ..models import MailUser

logger = logging.getLogger("backend")

# EC-20: Maximum allowed input lengths
_MAX_EMAIL_LENGTH = 254
_MAX_PASSWORD_LENGTH = 128


class UserService:
    @staticmethod
    def get_active_count() -> int:
        try:
            return MailUser.objects.filter(is_active=True).count()
        except OperationalError:
            logger.exception("Failed to fetch active user count")
            return 0

    @staticmethod
    def get_all_users() -> QuerySet[MailUser]:
        return MailUser.objects.order_by("email")

    @staticmethod
    def get_user_by_email(email: str) -> MailUser | None:
        # EC-20: Validate input length before DB query
        if email and len(email) > _MAX_EMAIL_LENGTH:
            logger.warning("Email too long (%d chars): %s...", len(email), email[:50])
            return None
        try:
            return MailUser.objects.get(email=email)
        except MailUser.DoesNotExist:
            return None

    @staticmethod
    def create_user(email: str, password: str, is_active: bool = True, is_staff: bool = False) -> MailUser:
        # EC-20: Validate input lengths
        if not email or len(email) > _MAX_EMAIL_LENGTH:
            raise ValueError(f"Email must be 1-{_MAX_EMAIL_LENGTH} characters")
        if len(password) > _MAX_PASSWORD_LENGTH:
            raise ValueError(f"Password must not exceed {_MAX_PASSWORD_LENGTH} characters")
        return MailUser.objects.create_user(
            email=email, password=password, is_active=is_active, is_staff=is_staff,
        )

    @staticmethod
    def has_staff_users() -> bool:
        try:
            return MailUser.objects.filter(is_staff=True, is_active=True).exists()
        except Exception:
            return False

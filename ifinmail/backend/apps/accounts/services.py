"""User management service layer."""
import logging

from django.db.utils import OperationalError

from .models import MailUser

logger = logging.getLogger("backend")


class UserService:
    @staticmethod
    def get_active_count():
        try:
            return MailUser.objects.filter(is_active=True).count()
        except OperationalError:
            logger.exception("Failed to fetch active user count")
            return 0

    @staticmethod
    def get_all_users():
        return MailUser.objects.order_by("email")

    @staticmethod
    def get_user_by_email(email: str):
        try:
            return MailUser.objects.get(email=email)
        except MailUser.DoesNotExist:
            return None

    @staticmethod
    def create_user(email: str, password: str, is_active: bool = True):
        return MailUser.objects.create_user(
            email=email, password=password, is_active=is_active
        )

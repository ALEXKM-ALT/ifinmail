"""Mail service layer."""
import logging

from django.db.utils import OperationalError

from .models import Alias, Mailbox

logger = logging.getLogger("backend")


class MailService:
    @staticmethod
    def get_mailbox_count():
        try:
            return Mailbox.objects.count()
        except OperationalError:
            logger.exception("Failed to fetch mailbox count")
            return 0

    @staticmethod
    def get_mailboxes_for_domain(domain_name: str):
        return Mailbox.objects.filter(
            domain__name=domain_name
        ).order_by("local_part")

    @staticmethod
    def get_aliases_for_domain(domain_name: str):
        return Alias.objects.filter(
            domain__name=domain_name
        ).order_by("source")

    @staticmethod
    def create_mailbox(domain, local_part: str, quota_bytes: int = 0):
        return Mailbox.objects.create(
            domain=domain,
            local_part=local_part,
            quota_bytes=quota_bytes,
        )

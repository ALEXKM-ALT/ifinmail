"""Mail service layer."""
import logging

from django.db import transaction
from django.db.models import QuerySet
from django.db.utils import OperationalError

from ..models import Alias, Mailbox

logger = logging.getLogger("backend")


class MailService:
    @staticmethod
    def get_mailbox_count() -> int:
        try:
            return Mailbox.objects.count()
        except OperationalError:
            logger.exception("Failed to fetch mailbox count")
            return 0

    @staticmethod
    def get_mailboxes_for_domain(domain_name: str) -> QuerySet[Mailbox]:
        return Mailbox.objects.filter(
            domain__name=domain_name
        ).order_by("local_part")

    @staticmethod
    def get_aliases_for_domain(domain_name: str) -> QuerySet[Alias]:
        return Alias.objects.filter(
            domain__name=domain_name
        ).order_by("source")

    @staticmethod
    def create_mailbox(domain: object, local_part: str, quota_bytes: int = 0) -> Mailbox:
        return Mailbox.objects.create(
            domain=domain,
            local_part=local_part,
            quota_bytes=quota_bytes,
        )

    @staticmethod
    def get_or_create_mailbox(domain: object, local_part: str) -> tuple[Mailbox, bool]:
        return Mailbox.objects.get_or_create(
            domain=domain, local_part=local_part,
        )

    @staticmethod
    def delete_mailbox(mailbox_id: str) -> bool:
        try:
            deleted, _ = Mailbox.objects.filter(id=mailbox_id).delete()
            return deleted > 0
        except OperationalError:
            return False

    @staticmethod
    def delete_alias(alias_id: str) -> bool:
        try:
            deleted, _ = Alias.objects.filter(id=alias_id).delete()
            return deleted > 0
        except OperationalError:
            return False

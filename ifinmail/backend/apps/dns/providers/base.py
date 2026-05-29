"""Abstract DNS provider interface."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class DNSRecord:
    type: str  # A, MX, TXT, CNAME
    name: str  # @ for root, subdomain name otherwise
    value: str  # record value
    priority: int = 0  # MX priority
    ttl: int = 3600


@dataclass
class DNSResult:
    success: bool
    message: str
    records_created: list[str] = field(default_factory=list)
    records_failed: list[str] = field(default_factory=list)


class BaseDNSProvider(Protocol):
    """Protocol that all DNS provider backends must implement."""

    provider_name: str

    def configure_domain(self, domain: str, records: list[DNSRecord]) -> DNSResult:
        """Create or update DNS records for a domain. Returns per-record results."""
        ...

    def verify_records(self, domain: str) -> dict[str, bool]:
        """Check whether expected records exist for a domain. Returns {record_type: exists}."""
        ...

    def get_nameservers(self, domain: str) -> list[str]:
        """Return the authoritative nameservers for this domain."""
        ...

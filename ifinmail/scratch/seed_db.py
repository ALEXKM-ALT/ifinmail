# ruff: noqa: E402
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings.development')
django.setup()

from backend.apps.dns.models import DNSProviderConfig
from backend.apps.domains.models import Domain
from backend.apps.mail.models import Alias, Mailbox
from backend.services.audit import AuditService

# Clear existing objects in unmanaged tables to keep it idempotent
Domain.objects.all().delete()
Mailbox.objects.all().delete()
Alias.objects.all().delete()
DNSProviderConfig.objects.all().delete()

print('Seeding domains...')
d1 = Domain.objects.create(
    name='example.com',
    verified=True,
    mx_verified=True,
    spf_verified=True,
    dkim_verified=True,
    dmarc_verified=True,
)
d2 = Domain.objects.create(
    name='staging.ifinmail.net',
    verified=True,
    mx_verified=True,
    spf_verified=False,
    dkim_verified=True,
    dmarc_verified=False,
)
d3 = Domain.objects.create(
    name='custom-domain.org',
    verified=False,
    mx_verified=False,
    spf_verified=False,
    dkim_verified=False,
    dmarc_verified=False,
)

print('Seeding mailboxes...')
Mailbox.objects.create(domain=d1, local_part='admin', quota_bytes=10737418240)  # 10 GB
Mailbox.objects.create(domain=d1, local_part='user', quota_bytes=2147483648)  # 2 GB
Mailbox.objects.create(domain=d2, local_part='support', quota_bytes=5368709120)  # 5 GB

print('Seeding aliases...')
Alias.objects.create(domain=d1, source='postmaster', destination='admin@example.com')
Alias.objects.create(domain=d1, source='info', destination='user@example.com,admin@example.com')

print('Seeding DNS provider configs...')
DNSProviderConfig.objects.create(
    provider='cloudflare', credentials={'api_token': 'mock-cloudflare-token-12345'}
)

print('Seeding audit events...')
from backend.services.models import AuditEvent

AuditEvent.objects.all().delete()

AuditService.record(
    action='user_login', user='admin', detail='Successful login from 127.0.0.1', severity='info'
)
AuditService.record(
    action='domain_created', user='admin', detail='Registered domain example.com', severity='info'
)
AuditService.record(
    action='domain_verified',
    user='system',
    detail='Domain example.com verified successfully',
    severity='info',
)
AuditService.record(
    action='mailbox_created',
    user='admin',
    detail='Provisioned mailbox admin@example.com',
    severity='info',
)
AuditService.record(
    action='dns_sync_completed',
    user='system',
    detail='DNS records synchronized for staging.ifinmail.net via Cloudflare',
    severity='info',
)
AuditService.record(
    action='certificate_issued',
    user='system',
    detail="TLS certificate successfully issued for mail.example.com by Let's Encrypt",
    severity='success',
)
AuditService.record(
    action='disk_cleanup',
    user='system',
    detail='System logs rotation completed; freed 1.2 GB of disk space',
    severity='info',
)
AuditService.record(
    action='axes_lockout_reset',
    user='admin',
    detail='Reset axes lockout counter for user: helper@example.com',
    severity='warning',
)

print('Database seeding completed successfully!')

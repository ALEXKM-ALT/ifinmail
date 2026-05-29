"""DNS provider service layer."""

import hashlib
import logging
import os
import socket

from django.core import signing
from django.db.utils import OperationalError

from ..models import DNSProviderConfig
from ..providers.base import DNSRecord
from ..providers.cloudflare import CloudflareProvider
from ..providers.digitalocean import DigitalOceanProvider
from ..providers.porkbun import PorkbunProvider

logger = logging.getLogger('backend')

PROVIDER_MAP = {
    'cloudflare': (CloudflareProvider, {'api_token'}, 'API Token'),
    'porkbun': (PorkbunProvider, {'api_key', 'secret_key'}, 'API Key + Secret Key'),
    'digitalocean': (DigitalOceanProvider, {'api_token'}, 'API Token'),
}

_IPIFY_URL = 'https://api.ipify.org'
_DEFAULT_DNS_TTL = int(os.environ.get('DNS_TTL', '3600'))
_DKIM_KEY_DIR = os.environ.get('DKIM_KEY_DIR', '/etc/dkim')


class DNSService:
    @staticmethod
    def get_first_config() -> DNSProviderConfig | None:
        return DNSProviderConfig.objects.first()

    @staticmethod
    def get_config_by_provider(provider_name: str) -> DNSProviderConfig | None:
        try:
            return DNSProviderConfig.objects.filter(provider=provider_name).first()
        except OperationalError:
            return None

    @staticmethod
    def update_or_create_config(
        provider_name: str,
        credentials: dict,
    ) -> tuple[DNSProviderConfig, bool]:
        # Sign credentials before DB write so tampering is detected on read.
        signed_credentials = signing.dumps(credentials)
        config, created = DNSProviderConfig.objects.update_or_create(
            provider=provider_name,
            defaults={'credentials': signed_credentials},
        )
        # Return the usable in-memory shape while keeping the stored value signed.
        config.credentials = credentials
        return config, created

    @staticmethod
    def get_server_ip() -> str:
        """Auto-detect the server's public IPv4 address."""
        ip_check_url = os.environ.get('IP_CHECK_URL', _IPIFY_URL)
        try:
            import requests as req

            resp = req.get(ip_check_url, timeout=5)
            if resp.status_code == 200:
                ip = resp.text.strip()
                if ip.startswith('10.') or ip.startswith('192.168.') or ip.startswith('127.'):
                    logger.warning(
                        'Detected private IP %s via ipify, trying MAIL_HOSTNAME fallback',
                        ip,
                    )
                elif ip.startswith('172.'):
                    parts = ip.split('.')
                    if len(parts) == 4 and 16 <= int(parts[1]) <= 31:
                        logger.warning(
                            'Detected private IP %s via ipify, trying MAIL_HOSTNAME fallback',
                            ip,
                        )
                    else:
                        return ip
                else:
                    return ip
        except Exception:
            logger.exception('Failed to detect public IP via %s', ip_check_url)
        mail_hostname = os.environ.get('MAIL_HOSTNAME')
        if mail_hostname:
            try:
                resolved = socket.gethostbyname(mail_hostname)
                logger.info('Resolved MAIL_HOSTNAME %s to %s as fallback', mail_hostname, resolved)
                return resolved
            except Exception:
                logger.exception('Failed to resolve MAIL_HOSTNAME %s', mail_hostname)
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return '0.0.0.0'

    @staticmethod
    def get_provider(
        provider_name: str,
    ) -> CloudflareProvider | DigitalOceanProvider | PorkbunProvider | None:
        config = DNSService.get_config_by_provider(provider_name)
        if not config:
            return None
        cls, _, _ = PROVIDER_MAP[provider_name]
        try:
            decrypted = signing.loads(config.credentials)
        except (signing.BadSignature, TypeError):
            logger.exception(
                'Failed to decrypt credentials for %s; falling back to raw value',
                provider_name,
            )
            decrypted = config.credentials
        return cls(**decrypted)

    @staticmethod
    def build_records(domain: str, server_ip: str) -> list[DNSRecord]:
        mail_hostname = os.environ.get('MAIL_HOSTNAME', f'mail.{domain}')
        dkim_selector = os.environ.get('DKIM_SELECTOR', 'default')
        ttl = _DEFAULT_DNS_TTL

        dkim_value = ''
        dkim_pub_path = os.path.join(_DKIM_KEY_DIR, f'{dkim_selector}.{domain}.pub')
        if os.path.isfile(dkim_pub_path):
            try:
                with open(dkim_pub_path) as f:
                    dkim_value = ''.join(line.strip() for line in f if not line.startswith('-'))
            except OSError:
                pass

        mta_sts_id = (
            os.environ.get('MTA_STS_ID')
            or hashlib.sha256(f'mta-sts:{domain}:{mail_hostname}'.encode()).hexdigest()[:16]
        )

        dkim_txt_prefix = 'v=DKIM1; k=rsa; p='
        dkim_txt_value = (
            dkim_txt_prefix + dkim_value if dkim_value else 'v=DKIM1; k=rsa; p=<add-dkim-key>'
        )

        return [
            DNSRecord(type='A', name='@', value=server_ip, ttl=ttl),
            DNSRecord(type='A', name='mail', value=server_ip, ttl=ttl),
            DNSRecord(type='A', name='mta-sts', value=server_ip, ttl=ttl),
            DNSRecord(type='MX', name='@', value=mail_hostname, priority=10, ttl=ttl),
            DNSRecord(type='TXT', name='@', value='v=spf1 mx -all', ttl=ttl),
            DNSRecord(
                type='TXT',
                name='_dmarc',
                value=f'v=DMARC1; p=quarantine; rua=mailto:postmaster@{domain}',
                ttl=ttl,
            ),
            DNSRecord(type='TXT', name='_mta-sts', value=f'v=STSv1; id={mta_sts_id}', ttl=ttl),
            DNSRecord(
                type='TXT',
                name=f'{dkim_selector}._domainkey',
                value=dkim_txt_value,
                ttl=ttl,
            ),
        ]

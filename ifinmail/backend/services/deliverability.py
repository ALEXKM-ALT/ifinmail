"""Deliverability service — comprehensive email deliverability diagnostics."""

import logging
import os
import socket
import subprocess
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger('backend')

_IPIFY_URL = 'https://api.ipify.org'
_LETSENCRYPT_DIR = os.environ.get('LETSENCRYPT_DIR', '/etc/letsencrypt')
_MAIL_VHOSTS_DIR = os.environ.get('MAIL_VHOSTS_DIR', '/var/mail/vhosts')

# Common RBLs to check
_DEFAULT_RBLS = [
    'zen.spamhaus.org',
    'b.barracudacentral.org',
    'bl.spamcop.net',
    'dnsbl.sorbs.net',
    'psbl.surriel.com',
]

# External DNS resolvers for propagation check
_DEFAULT_RESOLVERS = ['8.8.8.8', '1.1.1.1', '9.9.9.9']


class DeliverabilityService:
    @staticmethod
    def run_all_checks(domain: str | None = None) -> dict[str, Any]:
        """Run all deliverability checks. Returns a dict of check results."""
        domain = domain or os.environ.get('DOMAIN', os.environ.get('MAIL_DOMAIN', ''))
        server_ip = DeliverabilityService._get_server_ip()
        mail_hostname = os.environ.get('MAIL_HOSTNAME', f'mail.{domain}' if domain else '')

        results: dict[str, Any] = {
            'timestamp': datetime.now(UTC).isoformat(),
            'domain': domain,
            'server_ip': server_ip,
            'mail_hostname': mail_hostname,
        }

        results['dns_propagation'] = DeliverabilityService._check_dns_propagation(domain)
        results['blacklists'] = DeliverabilityService._check_blacklists(server_ip)
        results['reverse_dns'] = DeliverabilityService._check_reverse_dns(server_ip, mail_hostname)
        results['port25'] = DeliverabilityService._check_port25(mail_hostname)
        results['tls'] = DeliverabilityService._check_tls()

        # Overall status
        statuses = [
            v.get('status') for v in results.values() if isinstance(v, dict) and 'status' in v
        ]
        if all(s == 'pass' for s in statuses):
            results['status'] = 'pass'
        elif 'fail' in statuses:
            results['status'] = 'fail'
        else:
            results['status'] = 'warn'

        return results

    @staticmethod
    def _get_resolvers() -> list[str]:
        raw = os.environ.get('DELIVERABILITY_DNS_RESOLVERS', '')
        if raw:
            return [r.strip() for r in raw.split(',') if r.strip()]
        return list(_DEFAULT_RESOLVERS)

    @staticmethod
    def _get_rbls() -> list[str]:
        raw = os.environ.get('DELIVERABILITY_RBLS', '')
        if raw:
            return [r.strip() for r in raw.split(',') if r.strip()]
        return list(_DEFAULT_RBLS)

    @staticmethod
    def _check_dns_propagation(domain: str) -> dict[str, Any]:
        """Verify DNS records resolve from external resolvers."""
        if not domain:
            return {
                'status': 'fail',
                'detail': 'No domain configured',
                'fix': 'Configure a domain first.',
            }

        dkim_selector = os.environ.get('DKIM_SELECTOR', 'default')
        checks = {
            'a': {'type': 'A', 'name': domain, 'status': 'unchecked', 'detail': ''},
            'mx': {'type': 'MX', 'name': domain, 'status': 'unchecked', 'detail': ''},
            'spf': {'type': 'TXT', 'name': domain, 'status': 'unchecked', 'detail': ''},
            'dkim': {
                'type': 'TXT',
                'name': f'{dkim_selector}._domainkey.{domain}',
                'status': 'unchecked',
                'detail': '',
            },
            'dmarc': {
                'type': 'TXT',
                'name': f'_dmarc.{domain}',
                'status': 'unchecked',
                'detail': '',
            },
        }

        resolvers = DeliverabilityService._get_resolvers()
        for key, record in checks.items():
            for resolver in resolvers:
                try:
                    result = subprocess.run(
                        ['dig', f'@{resolver}', '+short', record['type'], record['name']],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        checks[key]['status'] = 'pass'
                        checks[key]['detail'] = 'Resolves'
                        break
                except Exception:
                    continue
            if checks[key]['status'] == 'unchecked':
                checks[key]['status'] = 'fail'
                checks[key]['detail'] = 'Not resolving from external DNS'

        all_pass = all(c['status'] == 'pass' for c in checks.values())
        return {
            'status': 'pass' if all_pass else 'fail',
            'detail': 'All DNS records resolve'
            if all_pass
            else 'Some DNS records are not propagating',
            'fix': None
            if all_pass
            else 'Verify DNS records were created. Propagation can take up to 48 hours.',
            'records': checks,
        }

    @staticmethod
    def _check_blacklists(server_ip: str) -> dict[str, Any]:
        """Check if the server IP is listed on common RBLs."""
        if not server_ip or server_ip in ('0.0.0.0', '127.0.0.1'):
            return {
                'status': 'warn',
                'detail': 'Cannot check local IP',
                'fix': 'Run this check from the live server.',
                'listings': {},
            }

        # Build reverse IP for RBL query
        try:
            reversed_ip = '.'.join(reversed(server_ip.split('.')))
        except Exception:
            return {'status': 'warn', 'detail': 'Invalid IP format', 'fix': '', 'listings': {}}

        listings = {}
        listed_count = 0
        rbls = DeliverabilityService._get_rbls()
        for rbl in rbls:
            query = f'{reversed_ip}.{rbl}'
            try:
                result = subprocess.run(
                    ['dig', '+short', 'A', query],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                answers = [
                    line
                    for line in result.stdout.strip().split('\n')
                    if line and not line.startswith(';')
                ]
                is_listed = len(answers) > 0 and '127.' in result.stdout
                listings[rbl] = {
                    'listed': is_listed,
                    'detail': result.stdout.strip() if is_listed else 'Not listed',
                }
                if is_listed:
                    listed_count += 1
            except Exception:
                listings[rbl] = {'listed': False, 'detail': 'Check failed'}

        if listed_count == 0:
            return {
                'status': 'pass',
                'detail': 'Not on any blacklists',
                'fix': None,
                'listings': listings,
            }
        return {
            'status': 'fail',
            'detail': f'Listed on {listed_count} blacklist(s)',
            'fix': (
                "Visit the RBL's delisting page. Common causes: compromised account, "
                "open relay, or a previous owner sent spam."
            ),
            'listings': listings,
        }

    @staticmethod
    def _check_reverse_dns(server_ip: str, mail_hostname: str) -> dict[str, Any]:
        """Check that the server IP has a PTR record matching the mail hostname."""
        if not server_ip or server_ip in ('0.0.0.0', '127.0.0.1'):
            return {
                'status': 'warn',
                'detail': 'Cannot check rDNS locally',
                'fix': 'Run this check from the live server.',
            }

        try:
            result = subprocess.run(
                ['dig', '+short', '-x', server_ip],
                capture_output=True,
                text=True,
                timeout=10,
            )
            ptr = result.stdout.strip().rstrip('.').split('\n')[0] if result.stdout.strip() else ''
        except Exception as e:
            return {
                'status': 'warn',
                'detail': f'rDNS check failed: {e}',
                'fix': 'Verify your VPS provider supports PTR records.',
            }

        if not ptr:
            return {
                'status': 'fail',
                'detail': 'No PTR record found for server IP',
                'fix': (
                    f'Contact your VPS provider and request a reverse DNS (PTR) record '
                    f'for {server_ip} pointing to {mail_hostname}.'
                ),
            }

        if ptr == mail_hostname or ptr == mail_hostname.rstrip('.'):
            return {'status': 'pass', 'detail': f'PTR is {ptr}', 'fix': None}

        return {
            'status': 'warn',
            'detail': f'PTR is {ptr}, expected {mail_hostname}',
            'fix': (
                f'Contact your VPS provider and change the PTR record from {ptr} '
                f'to {mail_hostname}.'
            ),
        }

    @staticmethod
    def _check_port25(mail_hostname: str) -> dict[str, Any]:
        """Check if port 25 is reachable (critical for receiving email)."""
        host = mail_hostname or 'localhost'
        port = int(os.environ.get('SMTP_PORT_CHECK', '25'))
        try:
            sock = socket.create_connection((host, port), timeout=10)
            banner = sock.recv(1024).decode('utf-8', errors='replace').strip()
            sock.close()
        except TimeoutError:
            return {
                'status': 'warn',
                'detail': f'Connection timed out on port {port}',
                'fix': (
                    'Some VPS providers block port 25 by default. '
                    'Contact your provider to unblock it.'
                ),
            }
        except ConnectionRefusedError:
            return {
                'status': 'fail',
                'detail': f'Port {port} refused — Postfix may not be running',
                'fix': (
                    "Check that Postfix is running: docker compose ps postfix. "
                    "If it's not, restart the stack."
                ),
            }
        except OSError as e:
            return {
                'status': 'fail',
                'detail': f'Port {port} unreachable: {e}',
                'fix': 'Check firewall rules and VPS provider port 25 policy.',
            }

        if banner and ('220' in banner or 'ESMTP' in banner):
            return {'status': 'pass', 'detail': f'Port {port} accepting connections', 'fix': None}
        return {
            'status': 'warn',
            'detail': f'Unexpected banner: {banner[:80]}',
            'fix': 'Postfix may need restarting.',
        }

    @staticmethod
    def _check_tls() -> dict[str, Any]:
        """Check TLS certificate validity."""
        mail_hostname = os.environ.get('MAIL_HOSTNAME', '')
        domain = os.environ.get('DOMAIN', os.environ.get('MAIL_DOMAIN', ''))
        cert_paths = []
        if mail_hostname:
            cert_paths.append(
                os.path.join(_LETSENCRYPT_DIR, 'live', mail_hostname, 'fullchain.pem')
            )
        if domain and domain != mail_hostname:
            cert_paths.append(os.path.join(_LETSENCRYPT_DIR, 'live', domain, 'fullchain.pem'))

        if not cert_paths:
            return {
                'status': 'fail',
                'detail': 'No TLS certificate found — domain not configured',
                'fix': 'Set DOMAIN and MAIL_HOSTNAME environment variables.',
            }

        for cert_path in cert_paths:
            if not os.path.isfile(cert_path):
                continue
            try:
                result = subprocess.run(
                    ['openssl', 'x509', '-enddate', '-noout', '-in', cert_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    continue
                date_str = result.stdout.strip().split('=', 1)[1]
                end_date = datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z').replace(tzinfo=UTC)
                days = (end_date - datetime.now(UTC)).days
                if days > 30:
                    return {
                        'status': 'pass',
                        'detail': f'Valid for {days} days',
                        'days': days,
                        'fix': None,
                    }
                elif days > 7:
                    return {
                        'status': 'warn',
                        'detail': f'Expires in {days} days',
                        'days': days,
                        'fix': (
                            "Certificate renews automatically. If it doesn't, "
                            "check certbot container logs."
                        ),
                    }
                else:
                    return {
                        'status': 'fail',
                        'detail': f'Expires in {days} days',
                        'days': days,
                        'fix': 'Check certbot container: docker compose logs certbot',
                    }
            except Exception:
                continue

        return {
            'status': 'fail',
            'detail': 'No TLS certificate found',
            'fix': 'Run the SSL setup: docker compose run --rm certbot',
        }

    @staticmethod
    def _get_server_ip() -> str:
        """Get the server's public IP."""
        ip_check_url = os.environ.get('IP_CHECK_URL', _IPIFY_URL)
        try:
            import requests as req

            resp = req.get(ip_check_url, timeout=5)
            if resp.status_code == 200:
                return resp.text.strip()
        except Exception:
            pass
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return '0.0.0.0'

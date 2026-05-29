"""Mail views for ifinmail — autoconfig endpoints only."""

import os
from xml.sax.saxutils import escape as xml_escape

from django.http import HttpRequest, HttpResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET


def _get_mail_settings() -> dict[str, str]:
    """Return IMAP/SMTP server settings from environment."""
    hostname = os.environ.get('MAIL_HOSTNAME', '')
    domain = os.environ.get('MAIL_DOMAIN', os.environ.get('DOMAIN', ''))
    return {
        'hostname': hostname,
        'domain': domain,
    }


@require_GET
@cache_page(3600)
def autoconfig_mozilla(request: HttpRequest) -> HttpResponse:
    """Thunderbird / Mozilla autoconfig XML."""
    settings = _get_mail_settings()
    d = xml_escape(settings['domain'])
    h = xml_escape(settings['hostname'])
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<clientConfig version="1.1">
    <emailProvider id="{d}">
        <domain>{d}</domain>
        <displayName>{d} Mail</displayName>
        <displayShortName>{d}</displayShortName>
        <incomingServer type="imap">
            <hostname>{h}</hostname>
            <port>993</port>
            <socketType>SSL</socketType>
            <authentication>password-cleartext</authentication>
            <username>%EMAILADDRESS%</username>
        </incomingServer>
        <outgoingServer type="smtp">
            <hostname>{h}</hostname>
            <port>587</port>
            <socketType>STARTTLS</socketType>
            <authentication>password-cleartext</authentication>
            <username>%EMAILADDRESS%</username>
        </outgoingServer>
    </emailProvider>
</clientConfig>'''
    return HttpResponse(xml, content_type='application/xml')


@require_GET
@cache_page(3600)
def autoconfig_outlook(request: HttpRequest) -> HttpResponse:
    """Outlook / Microsoft autodiscover XML."""
    settings = _get_mail_settings()
    h = xml_escape(settings['hostname'])
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006">
  <Response xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a">
    <Account>
      <AccountType>email</AccountType>
      <Action>settings</Action>
      <Protocol>
        <Type>IMAP</Type>
        <Server>{h}</Server>
        <Port>993</Port>
        <LoginName>%EMAILADDRESS%</LoginName>
        <SPA>off</SPA>
        <SSL>on</SSL>
      </Protocol>
      <Protocol>
        <Type>SMTP</Type>
        <Server>{h}</Server>
        <Port>587</Port>
        <LoginName>%EMAILADDRESS%</LoginName>
        <SPA>off</SPA>
        <Encryption>TLS</Encryption>
      </Protocol>
    </Account>
  </Response>
</Autodiscover>"""
    return HttpResponse(xml, content_type='application/xml')

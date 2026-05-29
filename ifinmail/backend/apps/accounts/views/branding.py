"""Branding and identity view."""

import json
import logging
import os

from django.conf import settings as django_settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from backend.services.audit import AuditService

from .auth import _is_staff

logger = logging.getLogger('backend')

_BRANDING_OVERRIDES_FILE = os.environ.get(
    'BRANDING_OVERRIDES_PATH',
    os.path.join(os.environ.get('APP_DIR', '/app'), 'branding_overrides.json'),
)
_MEDIA_ROOT = getattr(
    django_settings, 'MEDIA_ROOT', os.path.join(os.environ.get('APP_DIR', '/app'), 'media')
)

# Available web-safe fonts for the selector
_WEB_FONTS = [
    ('Inter', 'Inter (System Default)'),
    ('system-ui', 'System UI'),
    ('Helvetica Neue', 'Helvetica Neue'),
    ('Arial', 'Arial'),
    ('Georgia', 'Georgia'),
    ('Roboto', 'Roboto'),
    ('Open Sans', 'Open Sans'),
    ('Lato', 'Lato'),
    ('Montserrat', 'Montserrat'),
    ('Source Sans Pro', 'Source Sans Pro'),
    ('Merriweather', 'Merriweather'),
    ('PT Sans', 'PT Sans'),
    ('Noto Sans', 'Noto Sans'),
]


def _load_overrides() -> dict:
    """Load branding overrides from JSON file."""
    try:
        if os.path.isfile(_BRANDING_OVERRIDES_FILE):
            with open(_BRANDING_OVERRIDES_FILE) as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning('Failed to read branding overrides: %s', e)
    return {}


def _save_overrides(data: dict) -> None:
    """Persist branding overrides to JSON file."""
    os.makedirs(os.path.dirname(_BRANDING_OVERRIDES_FILE) or '.', exist_ok=True)
    with open(_BRANDING_OVERRIDES_FILE, 'w') as f:
        json.dump(data, f, indent=2)


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
def branding_identity(request: HttpRequest) -> HttpResponse:
    """Branding and identity settings screen."""
    overrides = _load_overrides()
    primary_color = overrides.get('primary_color') or os.environ.get('BRAND_COLOR', '#0051D5')
    secondary_color = overrides.get('secondary_color') or os.environ.get(
        'BRAND_SECONDARY_COLOR', '#ECEEF0'
    )
    accent_color = overrides.get('accent_color') or os.environ.get('BRAND_ACCENT_COLOR', '#4EDEA3')
    heading_font = overrides.get('heading_font', 'Inter')
    body_font = overrides.get('body_font', 'Inter')
    favicon_url = overrides.get('favicon_url', '')

    # Current logo filename derived from brand config or environment
    brand = getattr(django_settings, 'BRAND_CONFIG', None)
    current_logo = brand.logo_url if brand and brand.logo_url else ''
    if not current_logo:
        current_logo = os.environ.get('BRAND_LOGO_FILENAME', 'header_logo_v2.png')
    logo_filename = current_logo.rsplit('/', 1)[-1] if current_logo else 'header_logo_v2.png'

    return render(
        request,
        'admin/branding_identity.html',
        {
            'active_section': 'general',
            'header_search_placeholder': 'Search settings...',
            'show_settings_icon': True,
            'primary_color': primary_color,
            'secondary_color': secondary_color,
            'accent_color': accent_color,
            'current_logo_filename': logo_filename,
            'heading_font': heading_font,
            'body_font': body_font,
            'favicon_url': favicon_url,
            'web_fonts': _WEB_FONTS,
            'MEDIA_URL': getattr(django_settings, 'MEDIA_URL', '/media/'),
        },
    )


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
@require_POST
def branding_save(request: HttpRequest) -> HttpResponse:
    """Save branding overrides (colors, fonts) and optional favicon upload."""
    overrides = _load_overrides()
    changed = False

    # Color fields
    for field in ('primary_color', 'secondary_color', 'accent_color'):
        val = request.POST.get(field, '').strip()
        if val:
            h = val.lstrip('#').strip()
            if h and len(h) in (3, 6) and all(c in '0123456789abcdefABCDEF' for c in h):
                overrides[field] = f'#{h}'
                changed = True

    # Font fields
    for field in ('heading_font', 'body_font'):
        val = request.POST.get(field, '').strip()
        if val:
            overrides[field] = val
            changed = True

    # Favicon upload
    uploaded = request.FILES.get('favicon')
    if uploaded:
        favicon_dir = os.path.join(_MEDIA_ROOT, 'branding')
        os.makedirs(favicon_dir, exist_ok=True)
        favicon_path = os.path.join(favicon_dir, 'favicon.ico')
        with open(favicon_path, 'wb+') as dest:
            for chunk in uploaded.chunks():
                dest.write(chunk)
        overrides['favicon_url'] = (
            f'{getattr(django_settings, "MEDIA_URL", "/media/")}branding/favicon.ico'
        )
        changed = True

    if changed:
        try:
            _save_overrides(overrides)
            AuditService.record(
                action='branding_saved',
                user=request.user.username if request.user.is_authenticated else None,
                detail='Branding overrides updated',
            )
        except OSError as e:
            logger.exception('Failed to save branding overrides: %s', e)
            return JsonResponse(
                {'status': 'err', 'error': str(e)},
                status=500,
                content_type='application/json; charset=utf-8',
            )

    return JsonResponse(
        {'status': 'ok', 'saved': changed},
        content_type='application/json; charset=utf-8',
    )


@login_required
@user_passes_test(_is_staff, login_url='accounts:login')
@require_POST
def branding_reset(request: HttpRequest) -> HttpResponse:
    """Reset all branding overrides to system defaults."""
    try:
        if os.path.isfile(_BRANDING_OVERRIDES_FILE):
            os.remove(_BRANDING_OVERRIDES_FILE)
        # Also remove uploaded favicon
        favicon_path = os.path.join(_MEDIA_ROOT, 'branding', 'favicon.ico')
        if os.path.isfile(favicon_path):
            os.remove(favicon_path)
        AuditService.record(
            action='branding_reset',
            user=request.user.username if request.user.is_authenticated else None,
            detail='Branding overrides cleared',
        )
    except OSError as e:
        logger.exception('Failed to reset branding: %s', e)
        return JsonResponse(
            {'status': 'err', 'error': str(e)},
            status=500,
            content_type='application/json; charset=utf-8',
        )

    return JsonResponse(
        {'status': 'ok'},
        content_type='application/json; charset=utf-8',
    )

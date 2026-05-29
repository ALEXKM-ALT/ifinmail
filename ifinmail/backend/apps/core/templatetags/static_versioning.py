"""Template tags for static asset cache versioning."""

from __future__ import annotations

from urllib.parse import urlencode

from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def versioned_css(path: str) -> str:
    """Return a CSS static URL with the configured cache-busting version."""
    url = static(path)
    version = str(getattr(settings, 'CSS_VERSION', '')).strip()
    if not version:
        return url

    separator = '&' if '?' in url else '?'
    return f'{url}{separator}{urlencode({"v": version})}'

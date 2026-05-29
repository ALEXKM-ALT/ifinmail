from __future__ import annotations

from django.template import Context, Template
from django.test import override_settings

from backend.config.server_context import server_context


@override_settings(CSS_VERSION='2026.05.29')
def test_versioned_css_appends_configured_version() -> None:
    rendered = Template(
        "{% load static_versioning %}{% versioned_css 'css/ifinmail-layout.css' %}"
    ).render(Context())

    assert rendered == '/static/css/ifinmail-layout.css?v=2026.05.29'


@override_settings(CSS_VERSION='')
def test_versioned_css_leaves_url_unmodified_without_version() -> None:
    rendered = Template(
        "{% load static_versioning %}{% versioned_css 'css/ifinmail-layout.css' %}"
    ).render(Context())

    assert rendered == '/static/css/ifinmail-layout.css'


@override_settings(CSS_VERSION='release 1')
def test_server_context_exposes_css_version() -> None:
    context = server_context(object())

    assert context['CSS_VERSION'] == 'release 1'

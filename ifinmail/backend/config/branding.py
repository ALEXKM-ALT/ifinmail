"""
Branding configuration for self-hosted deployments.
All values read from environment variables. Falls back to ifinmail defaults.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BrandingConfig:
    name: str = "ifinmail"
    tagline: str = "mail infrastructure"
    color: str = "#0051d5"            # primary accent (hex, no spaces)
    logo_url: str = ""                 # if empty, use inline SVG default
    favicon_url: str = ""              # if empty, use default icon

    @classmethod
    def from_env(cls) -> "BrandingConfig":
        raw_color = os.environ.get("BRAND_COLOR", "#0051d5").strip() or "#0051d5"
        return cls(
            name=os.environ.get("BRAND_NAME", "ifinmail").strip() or "ifinmail",
            tagline=os.environ.get("BRAND_TAGLINE", "mail infrastructure").strip(),
            color=cls._sanitize_hex_color(raw_color),
            logo_url=os.environ.get("BRAND_LOGO_URL", "").strip(),
            favicon_url=os.environ.get("BRAND_FAVICON_URL", "").strip(),
        )

    @property
    def is_custom(self) -> bool:
        return self.name != "ifinmail"

    @property
    def css_overrides(self) -> str:
        """Return a <style> block when brand color is overridden, else empty string."""
        safe_color = self._sanitize_hex_color(self.color)
        if safe_color == "#0051d5":
            return ""
        return (
            f"<style>"
            f":root{{"
            f"--ifinmail-secondary:{safe_color};"
            f"--ifinmail-focus-ring-color:{self._hex_to_rgba(safe_color, 0.15)};"
            f"}}"
            f"</style>"
        )

    @property
    def logo_svg(self) -> str:
        """Inline SVG logo icon using the brand color."""
        c = self.color
        return (
            f'<svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true"'
            f' style="vertical-align:middle;margin-right:6px;">'
            f'<rect width="32" height="32" rx="6" fill="{c}"/>'
            f'<text x="16" y="21" text-anchor="middle"'
            f' font-family="Inter,-apple-system,BlinkMacSystemFont,sans-serif"'
            f' font-size="17" font-weight="700" fill="white">i</text>'
            f'</svg>'
        )

    @property
    def sidebar_logo_svg(self) -> str:
        """Larger inline SVG for the admin sidebar brand bar."""
        c = self.color
        return (
            f'<svg class="ifinmail-admin-brand-icon" width="32" height="32"'
            f' viewBox="0 0 32 32" aria-hidden="true">'
            f'<rect width="32" height="32" rx="6" fill="{c}"/>'
            f'<text x="16" y="21" text-anchor="middle"'
            f' font-family="Inter,-apple-system,BlinkMacSystemFont,sans-serif"'
            f' font-size="17" font-weight="700" fill="white">i</text>'
            f'</svg>'
        )

    @staticmethod
    def _sanitize_hex_color(color: str) -> str:
        """Sanitize a hex color value to prevent XSS in inline styles."""
        h = color.lstrip("#").strip()
        if not h or len(h) not in (3, 6) or not all(c in "0123456789abcdefABCDEF" for c in h):
            return "#0051d5"
        return f"#{h.lower()}"

    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: float) -> str:
        h = hex_color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"


def brand_context(request: object) -> dict[str, object]:
    """Context processor — injects brand into every template context."""
    from django.conf import settings

    brand = getattr(settings, "BRAND_CONFIG", None)
    if brand is None:
        brand = BrandingConfig()
    return {"brand": brand}

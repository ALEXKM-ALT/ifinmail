import json
import logging
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

from ifinmail.api.config import settings

logger = logging.getLogger("ifinmail.tracking")


def parse_user_agent(ua: str | None) -> dict:
    if not ua:
        return {"device_type": "unknown", "os": "unknown", "browser": "unknown"}

    ua_lower = ua.lower()

    device_type = "desktop"
    if any(p in ua_lower for p in ["iphone", "ipad", "ipod"]):
        device_type = "mobile" if "iphone" in ua_lower or "ipod" in ua_lower else "tablet"
    elif "android" in ua_lower:
        if "mobile" in ua_lower:
            device_type = "mobile"
        else:
            device_type = "tablet"
    elif "windows phone" in ua_lower:
        device_type = "mobile"
    elif "tablet" in ua_lower or "kindle" in ua_lower or "playbook" in ua_lower:
        device_type = "tablet"

    os = "unknown"
    if "windows" in ua_lower:
        os = "Windows"
    elif "mac os" in ua_lower or "macintosh" in ua_lower:
        os = "macOS"
    elif "linux" in ua_lower:
        os = "Linux"
    elif "android" in ua_lower:
        os = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os = "iOS"
    elif "cros" in ua_lower:
        os = "ChromeOS"

    browser = "unknown"
    if "edge" in ua_lower or "edg/" in ua_lower:
        browser = "Edge"
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser = "Opera"
    elif "chrome" in ua_lower and "chromium" not in ua_lower:
        browser = "Chrome"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "msie" in ua_lower or "trident" in ua_lower:
        browser = "Internet Explorer"

    return {"device_type": device_type, "os": os, "browser": browser}


GEOIP_CACHE: dict[str, dict] = {}


TRACKING_PIXEL_HTML = '<img src="{base}/analytics/track/{delivery_id}/open.gif" width="1" height="1" alt="" style="display:none" />'


def inject_tracking_pixel(html: str, delivery_id: int) -> str:
    pixel = TRACKING_PIXEL_HTML.format(base=settings.app_url.rstrip("/"), delivery_id=delivery_id)
    body_end = html.rfind("</body>")
    if body_end != -1:
        return html[:body_end] + pixel + html[body_end:]
    return html + pixel


def rewrite_links(html: str, delivery_id: int) -> str:
    base = settings.app_url.rstrip("/")

    def _replace_href(m: re.Match) -> str:
        original = m.group(0)
        url = m.group(1)
        tracked = f"{base}/analytics/track/{delivery_id}/click?url={quote(url, safe='')}"
        return original.replace(f'="{url}"', f'="{tracked}"').replace(f"='{url}'", f"='{tracked}'")

    html = re.sub(r'href\s*=\s*["\'](https?://[^"\']+)["\']', _replace_href, html, flags=re.IGNORECASE)
    return html


def inject_tracking(html: str, delivery_id: int) -> str:
    html = inject_tracking_pixel(html, delivery_id)
    html = rewrite_links(html, delivery_id)
    return html


def geo_lookup(ip: str) -> dict:
    if ip in GEOIP_CACHE:
        return GEOIP_CACHE[ip]
    if ip in ("127.0.0.1", "::1", "localhost"):
        result = {"city": "Local", "region": "Local", "country": "Local"}
        GEOIP_CACHE[ip] = result
        return result
    try:
        req = Request(f"https://ip-api.com/json/{ip}?fields=city,region,country", headers={"User-Agent": "ifinmail/1.0"}, method="GET")
        with urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            result = {
                "city": data.get("city") or "",
                "region": data.get("region") or "",
                "country": data.get("country") or "",
            }
            GEOIP_CACHE[ip] = result
            return result
    except Exception as exc:
        logger.debug("GeoIP lookup failed for %s: %s", ip, exc)
        return {"city": "", "region": "", "country": ""}

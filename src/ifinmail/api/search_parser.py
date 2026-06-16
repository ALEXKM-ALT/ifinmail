import re
from datetime import datetime

_OPERATORS = [
    (re.compile(r"\bfrom:(\S+)", re.IGNORECASE), "from_addr"),
    (re.compile(r"\bto:(\S+)", re.IGNORECASE), "to_addr"),
    (re.compile(r"\bsubject:\"([^\"]+)\"", re.IGNORECASE), "subject"),
    (re.compile(r"\bsubject:(\S+)", re.IGNORECASE), "subject"),
    (re.compile(r"\bhas:attachment(s)?\b", re.IGNORECASE), "has_attachment"),
    (re.compile(r"\bis:read\b", re.IGNORECASE), "read"),
    (re.compile(r"\bis:unread\b", re.IGNORECASE), "unread"),
    (re.compile(r"\bis:starred\b", re.IGNORECASE), "starred"),
    (re.compile(r"\bbefore:(\S+)", re.IGNORECASE), "before"),
    (re.compile(r"\bafter:(\S+)", re.IGNORECASE), "after"),
    (re.compile(r"\b(in|folder):(\S+)", re.IGNORECASE), "folder"),
    (re.compile(r"\blabel:(\S+)", re.IGNORECASE), "label"),
]


def parse_search(query: str | None) -> tuple[dict, str]:
    """
    Parse an advanced search query into structured filters and free-text.
    Returns (filters_dict, free_text).
    """
    filters: dict = {}
    if not query:
        return filters, ""

    text = query
    for pattern, key in _OPERATORS:
        match = pattern.search(text)
        if match:
            if key == "has_attachment":
                filters["has_attachment"] = True
            elif key == "read":
                filters["read"] = True
            elif key == "unread":
                filters["read"] = False
            elif key == "starred":
                filters["starred"] = True
            elif key == "before":
                filters["before"] = _parse_date(match.group(1))
            elif key == "after":
                filters["after"] = _parse_date(match.group(1))
            elif key in ("folder",):
                filters[key] = match.group(2).upper()
            elif key == "label":
                filters["label"] = match.group(1).upper()
            else:
                filters[key] = match.group(1)
            text = text[: match.start()] + text[match.end() :]

    text = text.strip()
    return filters, text


def _parse_date(raw: str) -> str | None:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(raw)
        return dt.isoformat()
    except (ValueError, TypeError):
        return None

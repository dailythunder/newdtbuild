import re
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return utcnow().isoformat().replace('+00:00', 'Z')


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return re.sub(r'-+', '-', text).strip('-')


def is_abs_http_url(value: Optional[str]) -> bool:
    return isinstance(value, str) and value.startswith(('http://', 'https://'))


def safe_str(value) -> str:
    if value is None:
        return ''
    return str(value)

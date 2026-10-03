"""Logika murni (tanpa dependensi frappe) agar mudah diuji."""
import hashlib
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

_env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]")
_MARKUP = re.compile(r"[*_~`]")


def date_range(window_days, tz_name="Asia/Jakarta", now=None):
    """(date_from, date_to) berformat YYYY-MM-DD. window_days=1 -> kemarin..hari ini."""
    now = now or datetime.now(ZoneInfo(tz_name))
    today = now.date()
    return (today - timedelta(days=int(window_days))).isoformat(), today.isoformat()


def render_variables(template, date_from, date_to, skip, take, account):
    context = {
        "date_from": date_from,
        "date_to": date_to,
        "today": date_to,
        "yesterday": (datetime.fromisoformat(date_to) - timedelta(days=1)).date().isoformat(),
        "skip": int(skip),
        "take": int(take),
        "account": account,
    }
    return _env.from_string(template).render(**context)


def get_path(obj, path, default=None):
    for part in str(path).split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            return default
    return obj


def sanitize_text(value, max_length=500):
    if value is None:
        return "-"
    text = _MARKUP.sub("", _CONTROL.sub("", str(value))).strip()
    if not text:
        return "-"
    return text if len(text) <= max_length else text[:max_length] + "…"


def should_remind(is_final, status_changed_at, last_reminder_at, now, minutes):
    """Reminder bila status tidak berubah >= minutes, lalu diulang tiap minutes."""
    if is_final or not status_changed_at:
        return False
    interval = timedelta(minutes=minutes)
    if now - status_changed_at < interval:
        return False
    return last_reminder_at is None or now - last_reminder_at >= interval


def cache_key(*parts):
    raw = "\x1f".join(str(p) for p in parts)
    return "apkt_monitor:rows:" + hashlib.md5(raw.encode()).hexdigest()

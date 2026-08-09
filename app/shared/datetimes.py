from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Pakistan Standard Time (PKT) = UTC+5
PKT_OFFSET = timedelta(hours=5)
PKT = timezone(PKT_OFFSET)


def now_pkt() -> datetime:
    """Return the current datetime in PKT (naive, no tzinfo)."""
    return datetime.now(PKT).replace(tzinfo=None)


def now_pkt_aware() -> datetime:
    """Return the current datetime in PKT with tzinfo."""
    return datetime.now(PKT)

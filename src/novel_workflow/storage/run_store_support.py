from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def legacy_time(events: list[Any]) -> str:
    times = [str(item.get("created_at") or "") for item in events if isinstance(item, dict) and item.get("created_at")]
    return max(times) if times else ""


def next_legacy_event_seq(events: list[Any]) -> int:
    values = [int(item.get("event_seq") or 0) for item in events if isinstance(item, dict)]
    return max(max(values, default=0), len(events)) + 1


def encode_cursor(value: tuple[str, str]) -> str:
    return base64.urlsafe_b64encode("|".join(value).encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(value: str) -> tuple[str, str] | None:
    if not value:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        timestamp, run_id = decoded.split("|", 1)
        return timestamp, run_id
    except (ValueError, UnicodeError, base64.binascii.Error):
        return None

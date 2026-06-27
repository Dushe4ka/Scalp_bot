"""Информация о сроке действия API-ключа Bybit (GET /v5/user/query-api)."""
from __future__ import annotations

from datetime import datetime, timezone

from pybit.unified_trading import HTTP

_EPOCH_EXPIRY = "1970-01-01T00:00:00Z"


def is_ip_bound(ips: list[str] | None) -> bool:
    return bool(ips) and ips != ["*"]


def parse_expired_at_from_result(result: dict) -> datetime | None:
    """Возвращает UTC datetime истечения ключа или None, если срок неизвестен."""
    ips = result.get("ips") or []
    if is_ip_bound(ips):
        return None

    deadline_day = result.get("deadlineDay")
    expired_at = result.get("expiredAt")
    if (
        deadline_day is None
        or int(deadline_day) < 0
        or not expired_at
        or expired_at == _EPOCH_EXPIRY
    ):
        return None

    try:
        dt = datetime.fromisoformat(str(expired_at).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None


def fetch_api_key_expired_at(session: HTTP) -> datetime | None:
    response = session.get_api_key_information()
    result = response.get("result") or {}
    return parse_expired_at_from_result(result)

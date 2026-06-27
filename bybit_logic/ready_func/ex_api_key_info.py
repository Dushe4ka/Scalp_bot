"""
Тест: срок действия API-ключа из .env (USE_DEMO + API_KEY/DEMO_API_KEY).

Запуск:
    python -m bybit_logic.ready_func.ex_api_key_info
"""
from __future__ import annotations

from datetime import datetime, timezone

from bybit_logic.bybit_func.api_key_info import fetch_api_key_expired_at, is_ip_bound
from bybit_logic.bybit_func.session import create_session
from bybit_logic.config import API_KEY, API_SECRET, DEMO_API_KEY, DEMO_API_SECRET
from config import USE_DEMO

_EPOCH_EXPIRY = "1970-01-01T00:00:00Z"


def _format_dt(raw: str | None) -> str:
    if not raw or raw == _EPOCH_EXPIRY:
        return "—"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return str(raw)


def print_api_key_expiry(use_demo: bool | None = None) -> None:
    demo = USE_DEMO if use_demo is None else use_demo
    if demo:
        api_key, api_secret = (DEMO_API_KEY or "").strip(), (DEMO_API_SECRET or "").strip()
        key_label = "DEMO_API_KEY"
    else:
        api_key, api_secret = (API_KEY or "").strip(), (API_SECRET or "").strip()
        key_label = "API_KEY"

    if not api_key or not api_secret:
        print(f"❌ В .env не заданы {key_label} / соответствующий secret (USE_DEMO={demo})")
        return

    session = create_session(use_demo=demo, api_key=api_key, api_secret=api_secret)
    response = session.get_api_key_information()
    result = response.get("result") or {}

    ips = result.get("ips") or []
    deadline_day = result.get("deadlineDay")
    expired_at_raw = result.get("expiredAt")
    created_at = result.get("createdAt")
    read_only = result.get("readOnly")
    note = result.get("note") or ""
    expired_at = fetch_api_key_expired_at(session)

    print(f"USE_DEMO={demo}")
    print(f"API key: {api_key[:6]}...{api_key[-4:]}")
    if note:
        print(f"Note: {note}")
    print(f"Read only: {'да' if read_only == 1 else 'нет'}")
    print(f"IP binding: {', '.join(ips) if ips else 'нет'}")
    print(f"Created: {_format_dt(created_at)}")

    if expired_at is not None:
        print(f"Expires: {expired_at.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"Days left: {deadline_day}")
    elif is_ip_bound(ips):
        print("Expires: неизвестно (ключ привязан к IP — Bybit не отдаёт deadlineDay/expiredAt)")
        print("Days left: —")
    else:
        print(f"Expires: {_format_dt(expired_at_raw)}")
        print(f"Days left: {deadline_day if deadline_day is not None else '—'}")
        print("ℹ️  Для ключей без IP срок обычно 90 дней; после смены пароля — 7 дней.")


if __name__ == "__main__":
    print_api_key_expiry()

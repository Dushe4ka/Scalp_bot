"""Чеклист онбординга пользователя в боте."""
from __future__ import annotations

from typing import Any


def _has_trade_sum(bybit_data: dict[str, Any]) -> bool:
    raw = bybit_data.get("sum_for_trades")
    if raw is None:
        return False
    try:
        return float(raw) > 0
    except (TypeError, ValueError):
        return bool(str(raw).strip() and str(raw).strip() not in {"0", "0.0"})


def get_onboarding_steps(
    user: dict[str, Any] | None,
    *,
    is_subscriber: bool,
    is_wait_confirm: bool,
) -> dict[str, bool]:
    bybit = (user or {}).get("bybit_data") or {}
    has_api = bool(str(bybit.get("api_key") or "").strip() and str(bybit.get("api_secret") or "").strip())
    return {
        "subscription_paid": is_subscriber or is_wait_confirm,
        "subscription_active": is_subscriber and not is_wait_confirm,
        "api_configured": has_api,
        "sum_configured": _has_trade_sum(bybit),
        "ready": is_subscriber and not is_wait_confirm and has_api and _has_trade_sum(bybit),
    }


def _step_icon(done: bool) -> str:
    return "✅" if done else "⬜"


def build_onboarding_checklist(
    user: dict[str, Any] | None,
    text_config: dict[str, Any],
    *,
    is_subscriber: bool,
    is_wait_confirm: bool,
) -> str:
    pt = text_config["profile_text"]
    steps = get_onboarding_steps(
        user,
        is_subscriber=is_subscriber,
        is_wait_confirm=is_wait_confirm,
    )
    lines = [
        pt["onboarding_checklist_title"],
        "",
        f"{_step_icon(steps['subscription_paid'])} {pt['onboarding_step_subscription']}",
        f"{_step_icon(steps['subscription_active'])} {pt['onboarding_step_wait_confirm']}",
        f"{_step_icon(steps['api_configured'])} {pt['onboarding_step_api']}",
        f"{_step_icon(steps['sum_configured'])} {pt['onboarding_step_sum']}",
        f"{_step_icon(steps['ready'])} {pt['onboarding_step_ready']}",
    ]
    if is_wait_confirm:
        lines.extend(["", pt["onboarding_wait_confirm_hint"]])
    elif steps["ready"]:
        lines.extend(["", pt["onboarding_all_done_hint"]])
    return "\n".join(lines)


async def is_trading_features_unlocked(user_id: int) -> bool:
    """Торговля, статистика и история — только после подтверждения подписки."""
    from database.users_repository import db

    is_subscriber = await db.is_subscriber(user_id)
    is_wait_confirm = await db.is_wait_sub_confirmation(user_id)
    return bool(is_subscriber and not is_wait_confirm)

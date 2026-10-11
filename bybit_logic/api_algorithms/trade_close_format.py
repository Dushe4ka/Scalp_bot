"""
Текст уведомления «Позиция закрыта» — общий для движка и сторожа (trade watchdog).

Вынесено из short_bu_ts_limit_engine, чтобы пользователь получал одинаковое сообщение
и при закрытии алгоритмом, и при закрытии вне алгоритма (вручную / мёртвая сессия).
"""
from __future__ import annotations

import time
from typing import Any


def price_change_percent(entry_price: float, exit_price: float, side: str | None) -> float:
    """% движения цены вход->выход, знак — по направлению позиции (совпадает со знаком PnL)."""
    if not entry_price:
        return 0.0
    if (side or "").strip() == "Buy":
        return ((exit_price - entry_price) / entry_price) * 100
    return ((entry_price - exit_price) / entry_price) * 100


def format_duration(seconds: float) -> str:
    """Длительность сделки в читаемом виде: "5 мин 32 сек" / "1 ч 12 мин"."""
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours} ч {minutes} мин"
    if minutes:
        return f"{minutes} мин {secs} сек"
    return f"{secs} сек"


def format_close_notification(
    close_info: dict[str, Any],
    *,
    symbol: str,
    position_side: str | None,
    created_at: float,
    show_source_note: bool = True,
    closed_at: float | None = None,
) -> str:
    pnl = float(close_info.get("pnl_usdt") or 0)
    pnl_sign = "+" if pnl >= 0 else ""
    source_note = ""
    source = close_info.get("source", "")
    if show_source_note and source == "trade_state":
        source_note = "\nℹ️ Итог по последней цене в алгоритме (Bybit ещё не отдал closed PnL)"
    elif show_source_note and source == "market_price":
        source_note = "\nℹ️ Итог по рыночной цене на момент проверки (Bybit не отдал closed PnL)"

    entry_price = float(close_info.get("entry_price") or 0)
    exit_price = float(close_info.get("exit_price") or 0)

    # Bybit's get_closed_pnl "side" отдаёт сторону закрывающего ордера (для шорта — "Buy"),
    # а не сторону позиции — доверять ей нельзя, сторону передаёт вызывающий.
    change_pct = price_change_percent(entry_price, exit_price, position_side)
    pct_sign = "+" if change_pct >= 0 else ""
    result_line = f"📈 Итог: {pct_sign}{change_pct:.2f}% ({pnl_sign}{pnl:.2f} USDT)"
    end_ts = closed_at if closed_at is not None else time.time()
    duration_text = format_duration(end_ts - created_at)

    return (
        "🔄 Позиция закрыта\n\n"
        f"📊 Символ: {close_info.get('symbol') or symbol}\n"
        f"💰 Цена входа: {entry_price:.8g}\n"
        f"💸 Цена выхода: {exit_price:.8g}\n"
        f"{result_line}"
        f"{source_note}\n"
        f"⏱ Длительность: {duration_text}"
    )

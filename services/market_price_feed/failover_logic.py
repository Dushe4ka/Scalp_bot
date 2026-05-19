"""Failover helpers without WebSocket / pybit dependencies (unit-testable)."""
from __future__ import annotations

import threading
import time
from typing import Any

from bybit_logic.feeds.redis_market_keys import FeedSource


class LegState:
    def __init__(self, name: FeedSource) -> None:
        self.name = name
        self.last_tick_ts: float = 0.0
        self._lock = threading.Lock()

    def mark_tick(self) -> None:
        with self._lock:
            self.last_tick_ts = time.time()

    def age_sec(self) -> float:
        with self._lock:
            if self.last_tick_ts <= 0:
                return float("inf")
            return time.time() - self.last_tick_ts

    def is_stale(self, stale_sec: float) -> bool:
        return self.age_sec() > stale_sec


def extract_ticker_price(message: dict[str, Any]) -> float | None:
    try:
        data = message.get("data")
        if isinstance(data, list):
            data = data[0] if data else None
        if not data:
            return None
        price = float(data.get("lastPrice", 0))
        return price if price > 0 else None
    except (TypeError, ValueError):
        return None


def maybe_failover(
    *,
    active: FeedSource,
    primary: LegState,
    backup: LegState,
    stale_sec: float,
    hysteresis_sec: float,
    last_failover_ts: float,
) -> tuple[FeedSource, float]:
    """
    Returns (new_active, new_last_failover_ts).
    """
    now = time.time()
    active_leg = primary if active == FeedSource.PRIMARY else backup
    standby_leg = backup if active == FeedSource.PRIMARY else primary

    if not active_leg.is_stale(stale_sec):
        if (
            active == FeedSource.BACKUP
            and not primary.is_stale(stale_sec)
            and (now - last_failover_ts) >= hysteresis_sec
        ):
            return FeedSource.PRIMARY, now
        return active, last_failover_ts

    if standby_leg.is_stale(stale_sec):
        return active, last_failover_ts

    new_active = standby_leg.name
    if new_active != active:
        return new_active, now
    return active, last_failover_ts

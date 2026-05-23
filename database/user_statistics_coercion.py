"""Normalize users.statistics fields to numeric types before $inc."""
from __future__ import annotations

from typing import Any


def statistics_coerce_update(stats: dict[str, Any] | None) -> dict[str, float | int]:
    """Build $set fields when statistics values are strings or invalid."""
    stats = stats or {}
    out: dict[str, float | int] = {}

    for key, default in (
        ("total_pnl", 0.0),
        ("sum_positive_trades", 0.0),
        ("sum_negative_trades", 0.0),
    ):
        val = stats.get(key)
        if isinstance(val, str):
            try:
                out[f"statistics.{key}"] = float(val.replace(",", ".").strip())
            except (TypeError, ValueError):
                out[f"statistics.{key}"] = default
        elif val is not None and not isinstance(val, (int, float)):
            out[f"statistics.{key}"] = default

    for key in ("total_trades", "positive_trades", "negative_trades"):
        val = stats.get(key)
        if isinstance(val, str):
            try:
                out[f"statistics.{key}"] = int(float(val.replace(",", ".").strip()))
            except (TypeError, ValueError):
                out[f"statistics.{key}"] = 0
        elif val is not None and not isinstance(val, (int, float)):
            out[f"statistics.{key}"] = 0

    return out


def coerce_user_statistics_sync(collection, tg_id: int) -> None:
    user = collection.find_one({"tg_id": int(tg_id)}, {"statistics": 1})
    if not user:
        return
    sets = statistics_coerce_update(user.get("statistics"))
    if sets:
        collection.update_one({"tg_id": int(tg_id)}, {"$set": sets})

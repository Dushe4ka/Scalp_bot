"""Env-конфигурация demo-показа сделок для маркетинга (изолированный Celery-воркер)."""
from __future__ import annotations

import os

import dotenv

dotenv.load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes")


# ВАЖНО: DEMO_SHOWCASE_TG_ID НЕ должен одновременно быть активным реальным trading candidate
# (реальные Bybit-ключи + subscription=true + stop_trading=false в Mongo users) — иначе demo- и
# real-сессии для этого tg_id столкнутся на одном ключе идемпотентности
# trade_cmd:{tg_id}:{symbol} (celery_app/trade_idempotency.py), и одна сессия может снять
# lock другой. См. docs/superpowers/specs/2026-08-11-demo-showcase-trading-design.md.
DEMO_SHOWCASE_ENABLED = _bool("DEMO_SHOWCASE_ENABLED", False)
DEMO_SHOWCASE_TG_ID = int(os.getenv("DEMO_SHOWCASE_TG_ID", "490882969"))
DEMO_SHOWCASE_NAME = os.getenv("DEMO_SHOWCASE_NAME", "demo_showcase")
DEMO_SHOWCASE_API_KEY = (os.getenv("DEMO_SHOWCASE_API_KEY") or "").strip()
DEMO_SHOWCASE_API_SECRET = (os.getenv("DEMO_SHOWCASE_API_SECRET") or "").strip()
DEMO_SHOWCASE_USDT_AMOUNT = float(os.getenv("DEMO_SHOWCASE_USDT_AMOUNT", "5000"))

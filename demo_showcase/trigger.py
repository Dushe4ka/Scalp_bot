"""Хук из /short_3_limit: параллельно реальным подписчикам ставит demo-сделку для маркетинга."""
from __future__ import annotations

from demo_showcase.config import DEMO_SHOWCASE_ENABLED
from logger_config import setup_logger

logger = setup_logger(__name__)


def maybe_trigger_demo_showcase(symbol: str) -> None:
    """Не срабатывает, если DEMO_SHOWCASE_ENABLED=false. Иначе ставит Celery-задачу в очередь demo_showcase."""
    if not DEMO_SHOWCASE_ENABLED:
        return

    from demo_showcase.tasks import demo_showcase_trade

    demo_showcase_trade.delay(symbol=symbol)
    logger.info("demo_showcase_trade поставлена в очередь: symbol=%s", symbol)

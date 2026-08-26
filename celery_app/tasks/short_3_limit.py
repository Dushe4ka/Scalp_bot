from celery_app.celery_config import celery_app
from logger_config import setup_logger
from celery_app.utils import setup_project_path

logger = setup_logger(__name__)

@celery_app.task(
    name='short_3_limit',
    bind=True,
    queue='trade_user',
    max_retries=3,
    default_retry_delay=5
)
def short_3_limit(
    self,
    symbol: str,
    tg_id: int,
    name: str,
    api_key: str,
    api_secret: str,
    sum_for_trades: float,
    trade_id: str | None = None,
    risk_mode: bool = False,
):
    """
    Маршрутизация short-сделки на engine-воркер (Phase 2 orchestrator).
    """
    setup_project_path()

    logger.info("🔄 short_3_limit route: symbol=%s tg_id=%s risk_mode=%s", symbol, tg_id, risk_mode)

    from celery_app.trade_orchestrator import assign_trade
    from celery_app.tasks.engine_execute_trade import engine_execute_trade

    assignment = assign_trade(
        symbol=symbol,
        tg_id=tg_id,
        name=name,
        api_key=api_key,
        api_secret=api_secret,
        sum_for_trades=float(sum_for_trades),
        trade_id=trade_id,
        risk_mode=risk_mode,
    )

    status = assignment.get("status")
    if status == "queued":
        logger.warning("Trade queued (all engines full): %s", assignment.get("trade_id"))
        return assignment

    if status != "assigned":
        return assignment

    queue = assignment["queue"]
    engine_execute_trade.apply_async(
        kwargs={
            "trade_id": assignment["trade_id"],
            "symbol": symbol,
            "tg_id": tg_id,
            "name": name,
            "api_key": api_key,
            "api_secret": api_secret,
            "sum_for_trades": float(sum_for_trades),
            "engine_id": assignment["engine_id"],
            "risk_mode": risk_mode,
        },
        queue=queue,
    )

    logger.info(
        "✅ short_3_limit routed: symbol=%s tg_id=%s engine=%s trade_id=%s",
        symbol,
        tg_id,
        assignment.get("engine_id"),
        assignment.get("trade_id"),
    )
    return assignment

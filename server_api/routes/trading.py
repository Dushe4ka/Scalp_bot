from fastapi import APIRouter, HTTPException, Request
from server_api.schemas import SymbolRequest
from logger_config import setup_logger
from celery_app.tasks.short_3_limit import short_3_limit
from celery_app.tasks.hedge_long_short_bu_ts import hedge_long_short_bu_ts_task
from celery_app.tasks.short_bu_ts_limit_nomulti import nomulti_short_bu_ts_limit_task
from bybit_logic.bybit_func import session, stop_trade, position
from server_api.utils import validate_and_clean_symbol
from config import USE_DEMO
from users_repository import db

router = APIRouter()
logger = setup_logger(__name__)

@router.post("/short_3_limit")
async def short_3_limit_endpoint(request: Request):
    """Запускает алгоритм short для символа (принимает текст)"""
    try:
        # Получаем тело запроса как текст
        body = await request.body()
        symbol = body.decode('utf-8').strip().upper()
        symbol = validate_and_clean_symbol(symbol)
        logger.info(f"🔍 Валидированный символ: {symbol}")

        if not symbol:
            raise HTTPException(status_code=400, detail="Символ не может быть пустым")
        
        users = await db.list_trading_candidates()
        queued = 0
        skipped_no_keys = 0
        skipped_stop_trading = 0
        skipped_invalid_sum = 0
        task_ids: list[str] = []

        for user in users:
            bybit_data = user.get("bybit_data") or {}
            api_key = (bybit_data.get("api_key") or "").strip()
            api_secret = (bybit_data.get("api_secret") or "").strip()
            stop_trading_flag = bybit_data.get("stop_trading") is True
            sum_for_trades_raw = bybit_data.get("sum_for_trades")

            if not api_key or not api_secret:
                skipped_no_keys += 1
                continue
            if stop_trading_flag:
                skipped_stop_trading += 1
                continue

            try:
                sum_for_trades = float(sum_for_trades_raw)
            except (TypeError, ValueError):
                skipped_invalid_sum += 1
                continue
            if sum_for_trades <= 0:
                skipped_invalid_sum += 1
                continue

            tg_id = int(user["tg_id"])
            name = user.get("name", "")
            task = short_3_limit.delay(
                symbol=symbol,
                tg_id=tg_id,
                name=name,
                api_key=api_key,
                api_secret=api_secret,
                sum_for_trades=sum_for_trades,
            )
            queued += 1
            task_ids.append(task.id)

        logger.info(
            "🚀 short_3_limit enqueued for symbol=%s queued=%s skipped_no_keys=%s skipped_stop_trading=%s skipped_invalid_sum=%s",
            symbol,
            queued,
            skipped_no_keys,
            skipped_stop_trading,
            skipped_invalid_sum,
        )
        return {
            "symbol": symbol,
            "status": "started",
            "queued": queued,
            "skipped_no_keys": skipped_no_keys,
            "skipped_stop_trading": skipped_stop_trading,
            "skipped_invalid_sum": skipped_invalid_sum,
            "task_ids": task_ids,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка запуска задачи: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nomulti_short_bu_ts_limit")
async def nomulti_short_bu_ts_limit_endpoint(request: Request):
    """Запуск немультюзерного short_bu_ts_limit по символу (одна Celery-задача)."""
    try:
        body = await request.body()
        symbol = body.decode("utf-8").strip().upper()
        symbol = validate_and_clean_symbol(symbol)
        logger.info("nomulti_short_bu_ts_limit: символ после валидации: %s", symbol)
        if not symbol:
            raise HTTPException(status_code=400, detail="Символ не может быть пустым")

        task = nomulti_short_bu_ts_limit_task.delay(symbol=symbol)
        return {
            "symbol": symbol,
            "status": "started",
            "task_id": task.id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка постановки nomulti_short_bu_ts_limit: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hedge_long_short_bu_ts")
async def hedge_long_short_bu_ts_endpoint(request: Request):
    """Запуск немультюзерного hedge long+short по символу (одна Celery-задача, ключи из config)."""
    try:
        body = await request.body()
        symbol = body.decode("utf-8").strip().upper()
        symbol = validate_and_clean_symbol(symbol)
        logger.info("hedge_long_short_bu_ts: символ после валидации: %s", symbol)
        if not symbol:
            raise HTTPException(status_code=400, detail="Символ не может быть пустым")

        task = hedge_long_short_bu_ts_task.delay(symbol=symbol)
        return {
            "symbol": symbol,
            "status": "started",
            "task_id": task.id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка постановки hedge_long_short_bu_ts: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop_trading_by_symbol")
async def stop_trading_by_symbol_endpoint(request: SymbolRequest):
    """Останавливает алгоритм short для символа"""
    try:
        logger.info(f"🔍 USE_DEMO из config: {USE_DEMO} (тип: {type(USE_DEMO)})")  # ✅ Для отладки
        http_session = session.create_session(use_demo=USE_DEMO)
        symbol = validate_and_clean_symbol(request.symbol)
        symbol = symbol.upper()
        stop_trade.stop_trading_by_symbol(symbol, http_session)
        return {"message": "Алгоритм остановлен"}
    except Exception as e:
        logger.error(f"❌ Ошибка остановки алгоритма: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop_trading_all")
async def stop_trading_all():
    """Останавливает все алгоритмы торговли"""
    try:
        logger.info(f"🔍 USE_DEMO из config: {USE_DEMO} (тип: {type(USE_DEMO)})")  # ✅ Для отладки
        http_session = session.create_session(use_demo=USE_DEMO)
        stop_trade.stop_all_trading(http_session)
        return {"message": "Все алгоритмы остановлены"}
    except Exception as e:
        logger.error(f"❌ Ошибка остановки всех алгоритмов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/result_position_info_by_symbol")
async def result_position_info_by_symbol(request: SymbolRequest):
    """Получает информацию о позиции"""
    try:
        logger.info(f"🔍 USE_DEMO из config: {USE_DEMO} (тип: {type(USE_DEMO)})")  # ✅ Для отладки
        http_session = session.create_session(use_demo=USE_DEMO)
        symbol = validate_and_clean_symbol(request.symbol)
        symbol = symbol.upper()
        result = position.result_position_info(symbol, http_session)
        return {"result": result}
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о позиции: {e}")
        raise HTTPException(status_code=500, detail=str(e))
from fastapi import APIRouter, HTTPException, Request
from server_api.schemas import SymbolRequest, CustomAlgoLaunchRequest, UserSymbolRequest, UserRequest
from logger_config import setup_logger
from celery_app.tasks.short_3_limit import short_3_limit
from celery_app.tasks.short_3_limit_nomulti import (
    ensure_nomulti_short_bu_ts_env,
    nomulti_short_3_limit_task,
)
from celery_app.tasks.hedge_long_short_bu_ts import hedge_long_short_bu_ts_task
from celery_app.tasks.custom_algo_nomulti import nomulti_custom_algo_task
from bybit_logic.bybit_func import session, stop_trade, position
from server_api.utils import validate_and_clean_symbol, get_user_http_session_or_404
from config import USE_DEMO
from database.users_repository import db
from database.custom_algo_repository import custom_algo_db, normalize_custom_config, CustomAlgoValidationError
from bybit_logic.feeds.feed_config import TRADE_SUBMIT_STAGGER_SEC
from celery_app.trade_idempotency import clear_all_trade_locks_for_user, clear_trade_lock

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

        from demo_showcase.trigger import maybe_trigger_demo_showcase

        maybe_trigger_demo_showcase(symbol)

        users = await db.list_trading_candidates()
        skipped_no_keys = 0
        skipped_stop_trading = 0
        skipped_invalid_sum = 0
        skipped_max_concurrent = 0
        trade_jobs: list[dict] = []

        from database.history_trades_repository import history_trades_db

        # 1) Сначала только проверка Mongo — кто реально может торговать
        for user in users:
            bybit_data = user.get("bybit_data") or {}
            api_key = (bybit_data.get("api_key") or "").strip()
            api_secret = (bybit_data.get("api_secret") or "").strip()
            stop_trading_flag = bybit_data.get("stop_trading") is True
            sum_for_trades_raw = bybit_data.get("sum_for_trades")
            tg_id = int(user["tg_id"])

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

            try:
                max_trades = int(bybit_data.get("max_concurrent_trades") or 1)
            except (TypeError, ValueError):
                max_trades = 1
            max_trades = max(1, max_trades)
            active_count = history_trades_db.count_active_trades(tg_id)
            if active_count >= max_trades:
                skipped_max_concurrent += 1
                logger.info(
                    "Пропуск tg_id=%s: активных сделок %s >= лимита %s",
                    tg_id,
                    active_count,
                    max_trades,
                )
                continue

            trade_jobs.append(
                {
                    "symbol": symbol,
                    "tg_id": tg_id,
                    "name": user.get("name", ""),
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "sum_for_trades": sum_for_trades,
                }
            )

        queued = len(trade_jobs)
        task_ids: list[str] = []

        # 2) Есть кому торговать → один WS на символ (feed), затем Celery
        if queued > 0:
            from bybit_logic.feeds.feed_symbol_request import request_feed_symbol

            request_feed_symbol(symbol)
            logger.info(
                "📡 Feed WS requested for %s before enqueue (%s user(s))",
                symbol,
                queued,
            )

            for index, job in enumerate(trade_jobs):
                countdown = index * TRADE_SUBMIT_STAGGER_SEC if TRADE_SUBMIT_STAGGER_SEC > 0 else 0
                task = short_3_limit.apply_async(kwargs=job, countdown=countdown)
                task_ids.append(task.id)

        logger.info(
            "🚀 short_3_limit enqueued for symbol=%s queued=%s skipped_no_keys=%s skipped_stop_trading=%s skipped_invalid_sum=%s skipped_max_concurrent=%s",
            symbol,
            queued,
            skipped_no_keys,
            skipped_stop_trading,
            skipped_invalid_sum,
            skipped_max_concurrent,
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


@router.post("/nomulti_short_3_limit")
async def nomulti_short_3_limit_endpoint(request: Request):
    """Запуск short BU TS limit для одного аккаунта: `short_bu_ts_limit` по ключам из .env, символ из тела."""
    try:
        body = await request.body()
        symbol = body.decode("utf-8").strip().upper()
        symbol = validate_and_clean_symbol(symbol)
        logger.info("nomulti_short_3_limit: символ после валидации: %s", symbol)
        if not symbol:
            raise HTTPException(status_code=400, detail="Символ не может быть пустым")

        try:
            ensure_nomulti_short_bu_ts_env()
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve)) from ve

        task = nomulti_short_3_limit_task.delay(symbol=symbol)
        return {
            "symbol": symbol,
            "status": "started",
            "task_id": task.id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка постановки nomulti_short_3_limit: %s", e)
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


@router.post("/nomulti_custom_algo")
async def nomulti_custom_algo_endpoint(request: CustomAlgoLaunchRequest):
    """Запуск custom nomulti алгоритма по символу с конфигурацией пользователя."""
    try:
        symbol = validate_and_clean_symbol(request.symbol).upper()
        if not symbol:
            raise HTTPException(status_code=400, detail="Символ не может быть пустым")

        config_doc = await custom_algo_db.get_by_tg_id(request.tg_id)
        if not config_doc:
            raise HTTPException(status_code=404, detail="Custom конфигурация не найдена")

        config = normalize_custom_config(config_doc)
        if request.order_amount_override is not None:
            if request.order_amount_override <= 0:
                raise HTTPException(status_code=400, detail="order_amount_override должен быть > 0")
            config["order_amount_usdt"] = float(request.order_amount_override)

        if config.get("order_amount_usdt") is None:
            raise HTTPException(status_code=400, detail="Не задана сумма сделки в конфиге или override")

        task = nomulti_custom_algo_task.delay(symbol=symbol, config=config)
        return {
            "symbol": symbol,
            "status": "started",
            "task_id": task.id,
        }
    except CustomAlgoValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка постановки nomulti_custom_algo: %s", e)
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


@router.post("/stop_trading_all_subscribers")
async def stop_trading_all_subscribers():
    """
    Останавливает торговлю у всех пользователей-кандидатов из БД
    (каждый пользователь — через его API key/secret).
    """
    try:
        users = await db.list_trading_candidates()
        processed = 0
        stopped = 0
        skipped_no_keys = 0
        errors: list[dict] = []

        for user in users:
            tg_id = int(user.get("tg_id") or 0)
            bybit_data = user.get("bybit_data") or {}
            api_key = (bybit_data.get("api_key") or "").strip()
            api_secret = (bybit_data.get("api_secret") or "").strip()
            if not api_key or not api_secret:
                skipped_no_keys += 1
                continue

            processed += 1
            try:
                http_session = session.create_session(
                    use_demo=USE_DEMO,
                    api_key=api_key,
                    api_secret=api_secret,
                )
                stop_trade.stop_all_trading(http_session)
                clear_all_trade_locks_for_user(tg_id)
                stopped += 1
            except Exception as e:
                logger.error("❌ stop_trading_all_subscribers error tg_id=%s: %s", tg_id, e)
                errors.append({"tg_id": tg_id, "error": str(e)})

        return {
            "message": "Массовая остановка торговли завершена",
            "processed": processed,
            "stopped": stopped,
            "skipped_no_keys": skipped_no_keys,
            "errors_count": len(errors),
            "errors": errors[:20],
        }
    except Exception as e:
        logger.error("❌ Ошибка stop_trading_all_subscribers: %s", e)
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


@router.post("/user_active_trades")
async def user_active_trades(request: UserRequest):
    """Возвращает активные позиции пользователя (по его API ключам)."""
    try:
        http_session = await get_user_http_session_or_404(request.tg_id)
        response = position.get_all_positions(http_session)
        rows = response.get("result", {}).get("list", []) if response else []
        active = []
        for row in rows:
            size = float(row.get("size", 0) or 0)
            if size <= 0:
                continue
            active.append(
                {
                    "symbol": str(row.get("symbol") or ""),
                    "side": str(row.get("side") or ""),
                    "size": size,
                    "entry_price": float(row.get("avgPrice", 0) or 0),
                    "position_idx": int(row.get("positionIdx", 0) or 0),
                    "open_time": row.get("createdTime"),
                }
            )
        return {"tg_id": int(request.tg_id), "active_trades": active}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Ошибка user_active_trades: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user_result_position_info_by_symbol")
async def user_result_position_info_by_symbol(request: UserSymbolRequest):
    """Текущая информация по позиции пользователя для символа."""
    try:
        http_session = await get_user_http_session_or_404(request.tg_id)
        symbol = validate_and_clean_symbol(request.symbol).upper()
        result = position.result_position_info_data(symbol, http_session)
        return {"tg_id": int(request.tg_id), "symbol": symbol, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Ошибка user_result_position_info_by_symbol: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user_stop_trading_by_symbol")
async def user_stop_trading_by_symbol(request: UserSymbolRequest):
    """Останавливает торговлю пользователя по символу (ордера + позиция)."""
    try:
        http_session = await get_user_http_session_or_404(request.tg_id)
        symbol = validate_and_clean_symbol(request.symbol).upper()
        stop_trade.stop_trading_by_symbol(symbol, http_session)
        clear_trade_lock(int(request.tg_id), symbol)
        return {"message": "Торговля по символу остановлена", "symbol": symbol}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Ошибка user_stop_trading_by_symbol: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user_stop_trading_all")
async def user_stop_trading_all(request: UserRequest):
    """Останавливает всю торговлю пользователя."""
    try:
        http_session = await get_user_http_session_or_404(request.tg_id)
        stop_trade.stop_all_trading(http_session)
        locks_cleared = clear_all_trade_locks_for_user(int(request.tg_id))
        return {
            "message": "Вся торговля пользователя остановлена",
            "tg_id": int(request.tg_id),
            "locks_cleared": locks_cleared,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Ошибка user_stop_trading_all: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
"""
Немультюзер: одновременный long + short по символу (linear hedge), плечо 10x,
стартовый SL 3%% на каждую ногу, БУ при +3%% прибыли по ноге, трейлинг шаг 2%% на каждую ногу.
"""
from __future__ import annotations

import os
import time

import dotenv

from bybit_logic.bybit_func import session, position, market, calculator, orders, stop_trade
from bybit_logic.bybit_func.price_stream import PriceStream
from bybit_logic.bybit_func.trailing_stop import TrailingStop
from celery_app.tasks.notifications import send_notification_task
from config import USE_DEMO
from logger_config import setup_logger

dotenv.load_dotenv()

logger = setup_logger(__name__)

# Bybit V5 linear hedge: positionIdx 1 = Buy leg, 2 = Sell leg
POSITION_IDX_BUY = 1
POSITION_IDX_SELL = 2

USDT_AMOUNT = float(os.getenv("HEDGE_USDT_AMOUNT", os.getenv("USDT_AMOUNT", "100")))
PNL_LOG_INTERVAL = float(os.getenv("PNL_LOG_INTERVAL", "5"))
CORRECTION_SL_PERCENTAGE = float(os.getenv("CORRECTION_SL_PERCENTAGE", "0.5"))

BU_TRIGGER_PCT = 3.0
INITIAL_SL_PCT = 3.0
TRAIL_STEP_PCT = 2.0
LEVERAGE = 10
BU_FIRST_TRAIL_PCT = BU_TRIGGER_PCT + TRAIL_STEP_PCT

SYMBOL: str | None = None
http_session = None
price_stream: PriceStream | None = None
should_stop = False

entry_buy: float | None = None
entry_sell: float | None = None
size_buy: float = 0.0
size_sell: float = 0.0

current_price: float | None = None
last_log_time = 0
last_position_check_time = 0.0

dual_open_seen = False
trigger_buy_done = False
trigger_sell_done = False

trailing_buy: TrailingStop | None = None
trailing_sell: TrailingStop | None = None
buy_leg_close_notified = False
sell_leg_close_notified = False


def _position_rows(sym: str) -> list[dict] | None:
    data = position.get_positions_by_symbol(http_session, sym)
    if data is None:
        return None
    if not data.get("result", {}).get("list"):
        return []
    return data["result"]["list"]


def _any_leg_open(sym: str) -> bool:
    rows = _position_rows(sym)
    if rows is None:
        return False
    for row in rows:
        if float(row.get("size", 0) or 0) > 0:
            return True
    return False


def _sync_legs_from_api(sym: str) -> bool:
    global entry_buy, entry_sell, size_buy, size_sell
    rows = _position_rows(sym)
    if rows is None:
        return False
    entry_buy = entry_sell = None
    size_buy = size_sell = 0.0
    for row in rows:
        side = row.get("side")
        sz = float(row.get("size", 0) or 0)
        ap = float(row.get("avgPrice", 0) or 0)
        if side == "Buy":
            size_buy = sz
            if sz > 0 and ap > 0:
                entry_buy = ap
        elif side == "Sell":
            size_sell = sz
            if sz > 0 and ap > 0:
                entry_sell = ap
    return True


def _try_switch_hedge(sym: str) -> None:
    try:
        position.switch_position_mode(http_session, sym, 3)
        logger.info("Режим позиции переключён в hedge для %s", sym)
    except Exception as e:
        logger.warning(
            "switch_position_mode (hedge) для %s: %s — продолжаем, возможно уже hedge",
            sym,
            e,
        )


def _price_trigger_buy() -> bool:
    global trailing_buy, SYMBOL, current_price, http_session, trigger_buy_done
    if current_price is None or SYMBOL is None or trailing_buy is None:
        return False
    logger.info("Long: цель +%s%% — ставлю БУ и трейлинг", BU_TRIGGER_PCT)
    ok, bu_price, _ = orders.set_stop_loss_with_breakeven_retries(
        SYMBOL,
        current_price,
        http_session,
        "Buy",
        correction_percent_start=CORRECTION_SL_PERCENTAGE,
        correction_percent_stop=2.0,
        correction_percent_step=0.5,
        position_idx=POSITION_IDX_BUY,
    )
    if not ok or bu_price is None:
        logger.error("Long: не удалось установить БУ")
        return False
    long_pct = (
        ((current_price - entry_buy) / entry_buy) * 100
        if entry_buy and entry_buy > 0
        else 0.0
    )
    trailing_buy.activate(current_price)
    if long_pct >= BU_FIRST_TRAIL_PCT:
        trailing_buy.set_initial_stop(current_price)
    send_notification_task.delay(
        f"🟢 Hedge {SYMBOL}: Long переведен в БУ\n"
        f"Цена: {current_price:.8g}\n"
        f"Изменение от входа: {long_pct:+.2f}%\n"
        f"Трейлинг: {TRAIL_STEP_PCT}%"
    )
    return True


def _price_trigger_sell() -> bool:
    global trailing_sell, SYMBOL, current_price, http_session, trigger_sell_done
    if current_price is None or SYMBOL is None or trailing_sell is None:
        return False
    logger.info("Short: цель +%s%% — ставлю БУ и трейлинг", BU_TRIGGER_PCT)
    ok, bu_price, _ = orders.set_stop_loss_with_breakeven_retries(
        SYMBOL,
        current_price,
        http_session,
        "Sell",
        correction_percent_start=CORRECTION_SL_PERCENTAGE,
        correction_percent_stop=2.0,
        correction_percent_step=0.5,
        position_idx=POSITION_IDX_SELL,
    )
    if not ok or bu_price is None:
        logger.error("Short: не удалось установить БУ")
        return False
    short_pct = (
        ((entry_sell - current_price) / entry_sell) * 100
        if entry_sell and entry_sell > 0
        else 0.0
    )
    trailing_sell.activate(current_price)
    if short_pct >= BU_FIRST_TRAIL_PCT:
        trailing_sell.set_initial_stop(current_price)
    send_notification_task.delay(
        f"🟢 Hedge {SYMBOL}: Short переведен в БУ\n"
        f"Цена: {current_price:.8g}\n"
        f"Изменение от входа: {short_pct:+.2f}%\n"
        f"Трейлинг: {TRAIL_STEP_PCT}%"
    )
    return True


def _force_protect_remaining_leg(closed_side: str) -> None:
    """
    Fail-safe: если одна нога уже закрылась, принудительно включаем БУ+трейлинг
    для оставшейся открытой ноги (если еще не включено).
    """
    global trigger_buy_done, trigger_sell_done
    if closed_side == "Buy":
        if size_sell > 0 and not trigger_sell_done:
            if _price_trigger_sell():
                trigger_sell_done = True
                logger.info("Fail-safe: после закрытия Long принудительно включен БУ/трейлинг для Short")
                send_notification_task.delay(
                    f"🛡 Hedge {SYMBOL}: Long закрыт, для Short принудительно включен БУ/трейлинг"
                )
    elif closed_side == "Sell":
        if size_buy > 0 and not trigger_buy_done:
            if _price_trigger_buy():
                trigger_buy_done = True
                logger.info("Fail-safe: после закрытия Short принудительно включен БУ/трейлинг для Long")
                send_notification_task.delay(
                    f"🛡 Hedge {SYMBOL}: Short закрыт, для Long принудительно включен БУ/трейлинг"
                )


def check_positions_and_exit(check_interval: float = 1.0) -> bool:
    """
    Обновляет размеры ног; при закрытии обеих — останавливает стрим и торговлю.
    Returns True если позиции изменились (размеры/цены входа).
    """
    global last_position_check_time, should_stop, price_stream, dual_open_seen
    global buy_leg_close_notified, sell_leg_close_notified
    global SYMBOL, http_session, current_price

    now = time.time()
    if now - last_position_check_time < check_interval:
        return False
    last_position_check_time = now

    if SYMBOL is None:
        return False

    prev_buy, prev_sell = size_buy, size_sell
    snap_eb, snap_es = entry_buy, entry_sell
    synced = _sync_legs_from_api(SYMBOL)
    if not synced:
        # Не считаем ноги закрытыми, если не удалось получить позиции (таймаут/сеть).
        logger.warning("Пропускаю check_positions_and_exit: позиции временно недоступны")
        return False

    if size_buy > 0 and size_sell > 0:
        dual_open_seen = True

    if prev_buy > 0 and size_buy <= 0 and not buy_leg_close_notified:
        buy_leg_close_notified = True
        long_pct = (
            ((current_price - snap_eb) / snap_eb) * 100
            if current_price and snap_eb and snap_eb > 0
            else 0.0
        )
        reason = "БУ/трейлинг" if trigger_buy_done else "стартовый SL/вне БУ"
        send_notification_task.delay(
            f"🔴 Hedge {SYMBOL}: Long закрыт\n"
            f"Последняя цена: {current_price}\n"
            f"Изменение от входа: {long_pct:+.2f}%\n"
            f"Причина (оценка): {reason}"
        )
        _force_protect_remaining_leg("Buy")

    if prev_sell > 0 and size_sell <= 0 and not sell_leg_close_notified:
        sell_leg_close_notified = True
        short_pct = (
            ((snap_es - current_price) / snap_es) * 100
            if current_price and snap_es and snap_es > 0
            else 0.0
        )
        reason = "БУ/трейлинг" if trigger_sell_done else "стартовый SL/вне БУ"
        send_notification_task.delay(
            f"🔴 Hedge {SYMBOL}: Short закрыт\n"
            f"Последняя цена: {current_price}\n"
            f"Изменение от входа: {short_pct:+.2f}%\n"
            f"Причина (оценка): {reason}"
        )
        _force_protect_remaining_leg("Sell")

    if dual_open_seen and size_buy <= 0 and size_sell <= 0:
        logger.info("Обе ноги закрыты — остановка мониторинга")
        stop_trade.stop_trading_by_symbol(SYMBOL, http_session)
        if price_stream:
            price_stream.stop()
        should_stop = True
        p_long = (
            ((current_price - snap_eb) / snap_eb) * 100
            if current_price and snap_eb and snap_eb > 0
            else 0.0
        )
        p_short = (
            ((snap_es - current_price) / snap_es) * 100
            if current_price and snap_es and snap_es > 0
            else 0.0
        )
        text = (
            f"🔄 Hedge: обе ноги закрыты\n\n"
            f"📊 {SYMBOL}\n"
            f"Последняя цена: {current_price}\n"
            f"Long от входа ~ {p_long:.2f}%\n"
            f"Short от входа ~ {p_short:.2f}%"
        )
        send_notification_task.delay(text)
        return True

    changed = (
        abs(size_buy - prev_buy) > 1e-12
        or abs(size_sell - prev_sell) > 1e-12
        or (entry_buy or 0) != (snap_eb or 0)
        or (entry_sell or 0) != (snap_es or 0)
    )
    return changed


def handle_ticker_price(message: dict) -> None:
    global current_price, last_log_time, should_stop
    global trigger_buy_done, trigger_sell_done, SYMBOL, http_session

    if should_stop:
        return

    try:
        if "data" not in message or not message["data"]:
            return
        ticker_data = message["data"]
        if isinstance(ticker_data, list):
            ticker_data = ticker_data[0]
        current_price = float(ticker_data.get("lastPrice", 0))
        if current_price <= 0:
            return

        check_positions_and_exit(check_interval=1.0)
        if should_stop:
            return

        long_pct = (
            ((current_price - entry_buy) / entry_buy) * 100
            if size_buy > 0 and entry_buy and entry_buy > 0
            else 0.0
        )
        short_pct = (
            ((entry_sell - current_price) / entry_sell) * 100
            if size_sell > 0 and entry_sell and entry_sell > 0
            else 0.0
        )

        if (
            size_buy > 0
            and long_pct >= BU_TRIGGER_PCT
            and not trigger_buy_done
        ):
            logger.info(
                "Long: достигнут порог БУ %.2f%% (текущее %.2f%%), попытка установки БУ/активации трейлинга",
                BU_TRIGGER_PCT,
                long_pct,
            )
            if _price_trigger_buy():
                trigger_buy_done = True

        if (
            size_sell > 0
            and short_pct >= BU_TRIGGER_PCT
            and not trigger_sell_done
        ):
            logger.info(
                "Short: достигнут порог БУ %.2f%% (текущее %.2f%%), попытка установки БУ/активации трейлинга",
                BU_TRIGGER_PCT,
                short_pct,
            )
            if _price_trigger_sell():
                trigger_sell_done = True

        if trailing_buy is not None and trailing_buy.is_active:
            if trailing_buy.update(current_price):
                st = trailing_buy.get_status()
                logger.info(
                    "Трейлинг long обновлён: стоп %s, цена %s",
                    st.get("last_stop_price"),
                    current_price,
                )
        if trailing_sell is not None and trailing_sell.is_active:
            if trailing_sell.update(current_price):
                st = trailing_sell.get_status()
                logger.info(
                    "Трейлинг short обновлён: стоп %s, цена %s",
                    st.get("last_stop_price"),
                    current_price,
                )

        ts = int(time.time())
        if int(PNL_LOG_INTERVAL) > 0 and ts % int(PNL_LOG_INTERVAL) == 0 and ts != last_log_time:
            last_log_time = ts
            logger.info(
                "Цена %.8g | long от входа: %.2f%% | short от входа: %.2f%% | size L/S: %.8g/%.8g",
                current_price,
                long_pct,
                short_pct,
                size_buy,
                size_sell,
            )
    except Exception as e:
        logger.error("Ошибка handle_ticker_price: %s", e)


def start_trading(symbol: str) -> None:
    global SYMBOL, http_session, price_stream, should_stop
    global entry_buy, entry_sell, size_buy, size_sell
    global last_position_check_time, last_log_time, current_price
    global dual_open_seen, trigger_buy_done, trigger_sell_done
    global trailing_buy, trailing_sell
    global buy_leg_close_notified, sell_leg_close_notified

    SYMBOL = symbol.upper()
    should_stop = False
    price_stream = None
    entry_buy = entry_sell = None
    size_buy = size_sell = 0.0
    last_position_check_time = 0.0
    last_log_time = 0
    current_price = None
    dual_open_seen = False
    trigger_buy_done = False
    trigger_sell_done = False
    trailing_buy = trailing_sell = None
    buy_leg_close_notified = False
    sell_leg_close_notified = False

    logger.info("=" * 50)
    logger.info("Hedge long+short: %s", SYMBOL)
    logger.info(
        "USDT на ногу: %s | плечо: %sx | SL старт: %s%% | БУ: +%s%% | трейлинг: %s%%",
        USDT_AMOUNT,
        LEVERAGE,
        INITIAL_SL_PCT,
        BU_TRIGGER_PCT,
        TRAIL_STEP_PCT,
    )
    logger.info("=" * 50)

    http_session = session.create_session(use_demo=USE_DEMO)

    if _any_leg_open(SYMBOL):
        logger.warning("По %s уже есть открытая нога — пропуск", SYMBOL)
        send_notification_task.delay(
            f"⚠️ Hedge: дубликат\n\n{SYMBOL}: уже есть открытая позиция"
        )
        return

    _try_switch_hedge(SYMBOL)
    try:
        position.set_isolated_margin(
            http_session,
            SYMBOL,
            buy_leverage=LEVERAGE,
            sell_leverage=LEVERAGE,
        )
        leverage_result = position.set_leverage(
            http_session,
            SYMBOL,
            buy_leverage=LEVERAGE,
            sell_leverage=LEVERAGE,
        )
        if not leverage_result.get("ok"):
            if leverage_result.get("error_type") == "leverage_too_high":
                max_lev = leverage_result.get("max_leverage")
                requested = leverage_result.get("requested_buy", LEVERAGE)
                msg = (
                    f"❌ Hedge {SYMBOL}: позиция не открыта\n"
                    f"Запрошено плечо: {requested}x\n"
                    f"📉Максимум по инструменту: {max_lev}x\n"
                    f"ℹ️По правилам проекта снижение плеча запрещено."
                )
                logger.error(msg)
                send_notification_task.delay(msg)
                return
            err = leverage_result.get("error", "unknown error")
            raise RuntimeError(f"set_leverage failed: {err}")
        if leverage_result.get("was_capped"):
            max_lev = leverage_result.get("max_leverage")
            applied = leverage_result.get("applied_buy")
            logger.warning(
                "Для %s запрошено плечо %sx, но биржа ограничила до %sx (max=%sx)",
                SYMBOL, LEVERAGE, applied, max_lev
            )
            send_notification_task.delay(
                f"⚠️ Hedge {SYMBOL}: плечо ограничено биржей\n"
                f"Запрошено: {LEVERAGE}x\n"
                f"Максимум биржи: {max_lev}x\n"
                f"Применено: {applied}x"
            )
    except Exception as e:
        logger.error("set_isolated_margin/set_leverage: %s", e)
        send_notification_task.delay(f"❌ Hedge {SYMBOL}: не удалось подготовить маржу/плечо: {e}")
        return

    qty = calculator.calculate_qty(SYMBOL, USDT_AMOUNT, http_session)
    logger.info("Qty на ногу: %s", qty)

    logger.info(
        "Отправляю Buy Market: symbol=%s qty=%s positionIdx=%s",
        SYMBOL,
        qty,
        POSITION_IDX_BUY,
    )
    r_buy = orders.place_order(
        SYMBOL, qty, "Buy", "Market", http_session, position_idx=POSITION_IDX_BUY
    )
    logger.info("Ответ Buy ордера: %s", r_buy)
    if not r_buy or r_buy.get("retCode") != 0:
        msg = r_buy.get("retMsg", "нет ответа") if r_buy else "нет ответа"
        logger.error("Ошибка входа Buy: %s | full_response=%s", msg, r_buy)
        send_notification_task.delay(f"❌ Hedge {SYMBOL}: Buy не открыт: {msg}")
        return

    logger.info(
        "Отправляю Sell Market: symbol=%s qty=%s positionIdx=%s",
        SYMBOL,
        qty,
        POSITION_IDX_SELL,
    )
    r_sell = orders.place_order(
        SYMBOL, qty, "Sell", "Market", http_session, position_idx=POSITION_IDX_SELL
    )
    logger.info("Ответ Sell ордера: %s", r_sell)
    if not r_sell or r_sell.get("retCode") != 0:
        msg = r_sell.get("retMsg", "нет ответа") if r_sell else "нет ответа"
        logger.error("Ошибка входа Sell: %s | full_response=%s — закрываю long", msg, r_sell)
        stop_trade.stop_trading_by_symbol(SYMBOL, http_session)
        send_notification_task.delay(f"❌ Hedge {SYMBOL}: Sell не открыт: {msg}")
        return

    time.sleep(1)
    if not _sync_legs_from_api(SYMBOL):
        logger.error("После входа не удалось прочитать позиции: get_positions недоступен")
        send_notification_task.delay(f"❌ Hedge {SYMBOL}: не удалось получить позиции после входа")
        return
    if size_buy <= 0 or size_sell <= 0 or not entry_buy or not entry_sell:
        logger.error("После входа не удалось прочитать обе ноги")
        stop_trade.stop_trading_by_symbol(SYMBOL, http_session)
        send_notification_task.delay(f"❌ Hedge {SYMBOL}: нет данных по обеим ногам")
        return

    sl_buy = calculator.calculate_stop_loss(entry_buy, INITIAL_SL_PCT, "Buy")
    sl_sell = calculator.calculate_stop_loss(entry_sell, INITIAL_SL_PCT, "Sell")
    orders.set_stop_loss(SYMBOL, sl_buy, http_session, position_idx=POSITION_IDX_BUY)
    orders.set_stop_loss(SYMBOL, sl_sell, http_session, position_idx=POSITION_IDX_SELL)
    logger.info("Стартовый SL long %s | short %s", sl_buy, sl_sell)

    trailing_buy = TrailingStop(
        symbol=SYMBOL,
        session=http_session,
        trigger_percentage=TRAIL_STEP_PCT,
        position_side="Buy",
        offset_percentage=0.1,
        position_idx=POSITION_IDX_BUY,
    )
    trailing_sell = TrailingStop(
        symbol=SYMBOL,
        session=http_session,
        trigger_percentage=TRAIL_STEP_PCT,
        position_side="Sell",
        offset_percentage=0.1,
        position_idx=POSITION_IDX_SELL,
    )

    last_position_check_time = time.time()
    dual_open_seen = size_buy > 0 and size_sell > 0

    send_notification_task.delay(
        f"🟢 Hedge {SYMBOL}: Long открыт\n"
        f"Entry: {entry_buy:.8g}\n"
        f"Qty: {size_buy:.8g}\n"
        f"SL старт: {sl_buy:.8g}\n"
        f"БУ: +{BU_TRIGGER_PCT}% | Трейлинг шаг: {TRAIL_STEP_PCT}%"
    )
    send_notification_task.delay(
        f"🟢 Hedge {SYMBOL}: Short открыт\n"
        f"Entry: {entry_sell:.8g}\n"
        f"Qty: {size_sell:.8g}\n"
        f"SL старт: {sl_sell:.8g}\n"
        f"БУ: +{BU_TRIGGER_PCT}% | Трейлинг шаг: {TRAIL_STEP_PCT}%"
    )

    price_stream = PriceStream(SYMBOL, handle_ticker_price, testnet=False)
    try:
        price_stream.run_forever()
    except KeyboardInterrupt:
        logger.info("Остановка по Ctrl+C")
    except Exception as e:
        logger.error("WebSocket: %s", e)
    finally:
        if should_stop:
            logger.info("Алгоритм завершён (обе ноги закрыты)")
        logger.info("start_trading hedge завершён")

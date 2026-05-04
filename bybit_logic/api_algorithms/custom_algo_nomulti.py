import os
import time

from bybit_logic.bybit_func import calculator, orders, position, session, stop_trade
from bybit_logic.bybit_func.price_stream import PriceStream
from bybit_logic.bybit_func.trailing_stop import TrailingStop
from custom_algo_repository import normalize_custom_config
from logger_config import setup_logger
from config import USE_DEMO

logger = setup_logger(__name__)

PNL_LOG_INTERVAL = float(os.getenv("PNL_LOG_INTERVAL", "5"))
CORRECTION_SL_PERCENTAGE = float(os.getenv("CORRECTION_SL_PERCENTAGE", "0.5"))
LEVERAGE = 10

current_price = None
entry_price = None
position_qty = None
position_side = None
price_stream = None
should_stop = False
last_pnl_log_ts = 0.0
last_position_check_ts = 0.0
breakeven_activated = False
trailing_stop = None
active_position_idx = None


def _reset_runtime():
    global current_price, entry_price, position_qty, position_side
    global price_stream, should_stop, last_pnl_log_ts, last_position_check_ts
    global breakeven_activated, trailing_stop, active_position_idx
    current_price = None
    entry_price = None
    position_qty = None
    position_side = None
    price_stream = None
    should_stop = False
    last_pnl_log_ts = 0.0
    last_position_check_ts = 0.0
    breakeven_activated = False
    trailing_stop = None
    active_position_idx = None


def _calc_profit_pct() -> float:
    if not entry_price or not current_price:
        return 0.0
    if position_side == "Buy":
        return ((current_price - entry_price) / entry_price) * 100
    return ((entry_price - current_price) / entry_price) * 100


def _select_position_row(rows: list[dict], side: str, position_idx: int | None) -> dict | None:
    if position_idx is not None:
        for row in rows:
            if int(row.get("positionIdx", 0) or 0) == int(position_idx):
                return row
    for row in rows:
        if row.get("side") == side:
            return row
    return rows[0] if rows else None


def _is_position_closed(http_session, symbol: str, side: str, position_idx: int | None) -> bool:
    info = position.get_positions_by_symbol(http_session, symbol)
    if not info or not info.get("result", {}).get("list"):
        return True
    row = _select_position_row(info["result"]["list"], side=side, position_idx=position_idx)
    if row is None:
        return True
    size = float(row.get("size", 0) or 0)
    return size <= 0


def _init_position_data(http_session, symbol: str, side: str, position_idx: int | None):
    global entry_price, position_qty
    info = position.get_positions_by_symbol(http_session, symbol)
    if not info or not info.get("result", {}).get("list"):
        raise RuntimeError(f"Не удалось получить позицию после входа для {symbol}")
    pos = _select_position_row(info["result"]["list"], side=side, position_idx=position_idx)
    if pos is None:
        raise RuntimeError(f"Не удалось выбрать строку позиции для {symbol} (side={side}, idx={position_idx})")
    entry_price = float(pos.get("avgPrice", 0) or 0)
    position_qty = float(pos.get("size", 0) or 0)
    if entry_price <= 0 or position_qty <= 0:
        raise RuntimeError(f"Некорректные параметры позиции для {symbol}: entry={entry_price}, qty={position_qty}")


def _handle_ticker_price(message: dict, http_session, symbol: str, cfg: dict, position_idx: int | None):
    global current_price, should_stop, last_pnl_log_ts, last_position_check_ts, breakeven_activated, trailing_stop

    data = message.get("data", {})
    raw_price = data.get("lastPrice")
    if raw_price in (None, ""):
        return

    current_price = float(raw_price)
    if current_price <= 0:
        return

    profit_pct = _calc_profit_pct()
    now = time.time()

    if now - last_pnl_log_ts >= PNL_LOG_INTERVAL:
        logger.info("📊 %s | side=%s | entry=%.8g | price=%.8g | pnl=%.2f%%", symbol, position_side, entry_price, current_price, profit_pct)
        last_pnl_log_ts = now

    if cfg["use_breakeven"] and not breakeven_activated and profit_pct >= cfg["breakeven_pct"]:
        ok, used_price, _ = orders.set_stop_loss_with_breakeven_retries(
            symbol=symbol,
            current_price=current_price,
            session=http_session,
            position_side=position_side,
            correction_percent_start=CORRECTION_SL_PERCENTAGE,
            position_idx=position_idx,
        )
        if ok:
            breakeven_activated = True
            logger.info("✅ БУ активирован для %s на %.8g", symbol, used_price if used_price else current_price)

    if cfg["use_trailing_stop"] and trailing_stop:
        if not trailing_stop.is_active and profit_pct >= cfg["trailing_activate_pct"]:
            if trailing_stop.activate(current_price):
                logger.info("🟢 Трейлинг активирован для %s", symbol)
        if trailing_stop.is_active:
            trailing_stop.update(current_price)

    if now - last_position_check_ts >= 1.0:
        last_position_check_ts = now
        if _is_position_closed(http_session, symbol, side=position_side, position_idx=position_idx):
            should_stop = True
            try:
                result_text = position.result_position_info(symbol, http_session)
                logger.info("✅ Информация о позиции получена!\nСообщение: %s", result_text)
            except Exception as e:
                logger.warning("Не удалось получить итог позиции для %s: %s", symbol, e)
            try:
                if price_stream:
                    price_stream.stop()
            except Exception:
                pass


def start_trading(symbol: str, config: dict):
    global price_stream, position_side, trailing_stop, active_position_idx
    _reset_runtime()

    symbol = symbol.strip().upper()
    cfg = normalize_custom_config(config)
    side = "Buy" if cfg["direction"] == "long" else "Sell"
    position_side = side
    order_amount_usdt = float(cfg["order_amount_usdt"])
    actual_usdt_for_qty = order_amount_usdt * 10

    http_session = session.create_session(use_demo=USE_DEMO)
    if position.if_position_open(http_session, symbol):
        raise RuntimeError(f"По {symbol} уже есть открытая позиция")

    lev_result = position.set_leverage(http_session, symbol, LEVERAGE)
    if not lev_result.get("ok"):
        raise RuntimeError(f"Не удалось установить плечо: {lev_result}")

    qty = calculator.calculate_qty(symbol, actual_usdt_for_qty, http_session)
    logger.info("Открытие custom позиции: %s %s qty=%s user_usdt=%s actual_usdt=%s", symbol, side, qty, order_amount_usdt, actual_usdt_for_qty)
    open_result = orders.place_order(symbol, qty, side, "Market", http_session)
    active_position_idx = None
    if not open_result or open_result.get("retCode") != 0:
        # Fallback: если аккаунт в hedge-mode, повторяем вход с positionIdx.
        hedge_idx = 1 if side == "Buy" else 2
        logger.warning(
            "Первичный вход не удался (%s). Пробую hedge fallback с positionIdx=%s",
            open_result,
            hedge_idx,
        )
        open_result = orders.place_order(symbol, qty, side, "Market", http_session, position_idx=hedge_idx)
        if open_result and open_result.get("retCode") == 0:
            active_position_idx = hedge_idx

    if not open_result or open_result.get("retCode") != 0:
        raise RuntimeError(f"Ошибка открытия позиции: {open_result}")

    _init_position_data(http_session, symbol, side=side, position_idx=active_position_idx)

    if cfg["use_stop_loss"]:
        sl_price = calculator.calculate_stop_loss(entry_price, cfg["stop_loss_pct"], side)
        sl_result = orders.set_stop_loss(symbol, sl_price, http_session, position_idx=active_position_idx)
        if not sl_result or sl_result.get("retCode") != 0:
            logger.warning("SL не установлен для %s: %s", symbol, sl_result)
        else:
            logger.info("✅ SL установлен для %s на %.8g", symbol, sl_price)

    if cfg["use_trailing_stop"]:
        trailing_stop = TrailingStop(
            symbol=symbol,
            session=http_session,
            trigger_percentage=cfg["trailing_step_pct"],
            position_side=side,
            offset_percentage=0.1,
            position_idx=active_position_idx,
        )

    def _price_handler(message: dict):
        _handle_ticker_price(message, http_session, symbol, cfg, active_position_idx)

    price_stream = PriceStream(symbol, _price_handler, testnet=USE_DEMO)
    logger.info("🚀 Запуск PriceStream custom_algo для %s", symbol)
    try:
        price_stream.run_forever()
    finally:
        if should_stop:
            try:
                stop_trade.stop_trading_by_symbol(symbol, http_session)
            except Exception:
                pass

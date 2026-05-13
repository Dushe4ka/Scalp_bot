from pybit.unified_trading import HTTP
from logger_config import setup_logger
from bybit_logic.bybit_func import calculator
from bybit_logic.bybit_func.market import get_qty_limits, get_price_limits
from bybit_logic.utils import frange
import math

logger = setup_logger(__name__)

def place_order(
    symbol,
    qty,
    side,
    order_type,
    session: HTTP,
    *,
    position_idx: int | None = None,
    reduce_only: bool = False,
):
    try:
        kwargs: dict = {
            "category": "linear",
            "symbol": symbol.upper(),
            "side": side,
            "orderType": order_type,
            "qty": qty,
        }
        if position_idx is not None:
            kwargs["positionIdx"] = position_idx
        if reduce_only:
            kwargs["reduceOnly"] = True
        logger.info("place_order request: %s", kwargs)
        return session.place_order(**kwargs)
    except Exception as e:
        logger.exception("Error placing order (%s %s): %s", symbol, side, e)
        return None

def place_limit_order(
    symbol,
    qty,
    side,
    price,
    session: HTTP,
    *,
    position_idx: int | None = None,
):
    try:
        kwargs: dict = {
            "category": "linear",
            "symbol": symbol.upper(),
            "side": side,
            "orderType": "Limit",
            "qty": qty,
            "price": price,
        }
        if position_idx is not None:
            kwargs["positionIdx"] = position_idx
        return session.place_order(**kwargs)
    except Exception as e:
        logger.error(f"Error placing limit order: {e}")
        return None

def get_open_orders_by_symbol(symbol, session: HTTP):
    try:
        return session.get_open_orders(
            category="linear",
            symbol=symbol.upper()
        )
    except Exception as e:
        logger.error(f"Error getting open orders: {e}")
        return None

def set_stop_loss(
    symbol,
    stop_loss_price,
    session: HTTP,
    *,
    position_idx: int | None = None,
):
    try:
        kwargs: dict = {
            "category": "linear",
            "symbol": symbol.upper(),
            "stopLoss": str(stop_loss_price),
        }
        if position_idx is not None:
            kwargs["positionIdx"] = position_idx
        return session.set_trading_stop(**kwargs)
    except Exception as e:
        logger.error(f"Error setting stop loss: {e}")
        return None


def _round_price_by_tick(price: float, tick_size: float, direction: str) -> float:
    """Округляет цену по шагу tickSize в нужную сторону."""
    if tick_size <= 0:
        return price
    if direction == "up":
        return math.ceil(price / tick_size) * tick_size
    return math.floor(price / tick_size) * tick_size


def _normalize_stop_loss_price(
    raw_price: float,
    current_price: float,
    position_side: str,
    tick_size: float,
) -> float:
    """
    Нормализует цену stopLoss с учетом ограничений биржи:
    - округление по tickSize;
    - для Sell stopLoss должен быть выше текущей цены;
    - для Buy stopLoss должен быть ниже текущей цены.
    """
    side = (position_side or "").strip()
    if side == "Sell":
        normalized = _round_price_by_tick(raw_price, tick_size, "up")
        if normalized <= current_price:
            normalized = _round_price_by_tick(current_price + tick_size, tick_size, "up")
        return normalized

    # По умолчанию обрабатываем как Buy
    normalized = _round_price_by_tick(raw_price, tick_size, "down")
    if normalized >= current_price:
        normalized = _round_price_by_tick(current_price - tick_size, tick_size, "down")
    return normalized

def place_n_limit_order(
    symbol,
    base_usdt_amount,
    side,
    base_price,
    session: HTTP,
    n: int,
    limit_percentage: float,
    *,
    position_idx: int | None = None,
):
    """
    Размещает n лимитных ордеров с экспоненциальным увеличением суммы и шагом процентного отличия
    
    Логика размещения ордеров:
    - 1-й ордер: base_usdt_amount USDT на цене, отличающейся на limit_percentage% от base_price
    - 2-й ордер: base_usdt_amount * 2 USDT на цене, отличающейся на limit_percentage * 2% от base_price
    - 3-й ордер: base_usdt_amount * 4 USDT на цене, отличающейся на limit_percentage * 3% от base_price
    - И так далее...
    
    Args:
        symbol: Символ торговой пары
        base_usdt_amount: Базовая сумма в USDT для первого ордера (например, 100)
        side: "Buy" или "Sell"
        base_price: Базовая цена входа (от которой считаются все проценты)
        session: HTTP сессия Bybit
        n: Количество ордеров для размещения
        limit_percentage: Базовый процент шага (например, 10 означает 10%, 20%, 30%...)
    
    Returns:
        Список результатов размещения ордеров или None в случае критической ошибки
    
    Пример:
        # Вход в лонг на 100 USDT, цена входа = 1.0
        # Разместить 3 ордера:
        # - 100 USDT на цене -10% от 1.0 = 0.9
        # - 200 USDT на цене -20% от 1.0 = 0.8
        # - 400 USDT на цене -30% от 1.0 = 0.7
        place_n_limit_order("BTCUSDT", 100, "Buy", 1.0, session, 3, 10.0)
    """
    results = []
    
    try:
        # Получаем лимиты для округления количества
        min_qty, step_size = get_qty_limits(symbol, session)
        
        for i in range(n):
            try:
                # 1. Рассчитываем сумму в USDT для текущего ордера
                # Формула: base * 2^i (100, 200, 400, 800...)
                order_usdt_amount = base_usdt_amount * (2 ** i)
                
                # 2. Рассчитываем процент отличия от базовой цены
                # Формула: limit_percentage * (i + 1) (10%, 20%, 30%...)
                order_percentage = limit_percentage * (i + 1)
                
                # 3. Рассчитываем цену лимитного ордера от базовой цены
                # Для Buy: цена ниже базовой (минус процент)
                # Для Sell: цена выше базовой (плюс процент)
                limit_price = calculator.calculate_limit_price(base_price, order_percentage, side)
                
                # 4. ✅ Рассчитываем количество монет для ордера на основе лимитной цены
                # qty = сумма_в_usdt / цена_ордера
                qty = order_usdt_amount / limit_price
                
                # 5. ✅ Округляем количество с учетом лимитов биржи (как в эталоне)
                if qty < min_qty:
                    qty = min_qty
                qty = calculator.round_by_step(qty, step_size)
                
                # 6. ✅ Проверяем, что после округления количество валидное
                # (округление floor может сделать qty меньше min_qty)
                if qty < min_qty:
                    logger.warning(f"⚠️ Ордер {i+1}/{n} пропущен: после округления количество ({qty}) меньше минимального ({min_qty})")
                    results.append({
                        'order_number': i + 1,
                        'usdt_amount': order_usdt_amount,
                        'price': limit_price,
                        'qty': qty,
                        'percentage': order_percentage,
                        'success': False,
                        'error': f'Qty {qty} меньше минимального {min_qty}'
                    })
                    continue
                
                # ✅ Рассчитываем фактический объем в USDT после округления
                actual_usdt_amount = qty * limit_price
                
                logger.info(f"Размещение ордера {i+1}/{n}:")
                logger.info(f"  💵 Целевая сумма: {order_usdt_amount} USDT")
                logger.info(f"  💰 Фактическая сумма: {actual_usdt_amount:.2f} USDT")
                logger.info(f"  📊 Цена: {limit_price} ({order_percentage:.1f}% от базовой {base_price})")
                logger.info(f"  🔢 Количество: {qty}")
                
                # Размещаем ордер
                result = place_limit_order(
                    symbol, qty, side, limit_price, session, position_idx=position_idx
                )
                
                if result and result.get('retCode') == 0:
                    results.append({
                        'order_number': i + 1,
                        'usdt_amount': order_usdt_amount,
                        'actual_usdt_amount': actual_usdt_amount,
                        'price': limit_price,
                        'qty': qty,
                        'percentage': order_percentage,
                        'result': result,
                        'success': True
                    })
                    logger.info(f"✅ Ордер {i+1}/{n} успешно размещен: orderId={result.get('result', {}).get('orderId')}")
                else:
                    error_msg = result.get('retMsg', 'Unknown error') if result else 'No response'
                    results.append({
                        'order_number': i + 1,
                        'usdt_amount': order_usdt_amount,
                        'actual_usdt_amount': actual_usdt_amount,
                        'price': limit_price,
                        'qty': qty,
                        'percentage': order_percentage,
                        'result': result,
                        'success': False,
                        'error': error_msg
                    })
                    logger.warning(f"⚠️ Ордер {i+1}/{n} не размещен: {error_msg}")
                
                # Небольшая задержка между запросами для избежания rate limit
                if i < n - 1:  # Не делаем задержку после последнего ордера
                    import time
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка при размещении ордера {i+1}/{n}: {e}")
                results.append({
                    'order_number': i + 1,
                    'success': False,
                    'error': str(e)
                })
                # Продолжаем размещать остальные ордера
        
        successful = sum(1 for r in results if r.get('success'))
        logger.info(f"📊 Итого размещено ордеров: {successful}/{n}")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при размещении n лимитных ордеров: {e}")
        return None


def set_stop_loss_with_breakeven_retries(
    symbol: str,
    current_price: float,
    session: HTTP,
    position_side: str,
    *,
    correction_percent_start: float = 0.5,
    correction_percent_stop: float = 2.0,
    correction_percent_step: float = 0.5,
    position_idx: int | None = None,
) -> tuple[bool, float | None, dict | None]:
    """
    Пытается выставить стоп-лосс (БУ): сначала на current_price, затем с отступами
    correction_percent_start … correction_percent_stop с шагом correction_percent_step
    (по умолчанию 0.5%, 1%, 1.5%, 2% через calculate_little_less_price).
    Возвращает (успех, цена_на_которой_сработало, последний_ответ_API).
    """
    percents = frange(
        correction_percent_start,
        correction_percent_stop,
        correction_percent_step,
    )
    prices_to_try: list[tuple[str, float]] = [("текущая цена", current_price)]
    for pct in percents:
        adjusted = calculator.calculate_little_less_price(
            current_price, pct, position_side
        )
        prices_to_try.append((f"отступ {pct:g}%", adjusted))

    try:
        _, tick_size = get_price_limits(symbol, session)
    except Exception as e:
        logger.warning("Не удалось получить tickSize для %s: %s", symbol, e)
        tick_size = 0.0

    # После нормализации разные raw-цены могут стать одинаковыми.
    seen_prices: set[float] = set()

    last_result: dict | None = None
    for label, raw_price in prices_to_try:
        price = _normalize_stop_loss_price(raw_price, current_price, position_side, tick_size)
        key = round(price, 12)
        if key in seen_prices:
            logger.debug("Пропускаю дубликат stopLoss после нормализации: %s", f"{price:.8g}")
            continue
        seen_prices.add(key)

        logger.info(
            "Попытка установки стоп-лосса (%s): %s (raw=%s, tick=%s)",
            label,
            f"{price:.8g}",
            f"{raw_price:.8g}",
            f"{tick_size:.8g}",
        )
        result = set_stop_loss(symbol, price, session, position_idx=position_idx)
        last_result = result
        if result and result.get("retCode") == 0:
            logger.info("Стоп-лосс установлен на %s (%s)", f"{price:.8g}", label)
            return True, price, result
        err = result.get("retMsg", "Неизвестная ошибка") if result else "Нет ответа"
        logger.warning("Стоп-лосс не принят (%s): %s", label, err)

    return False, None, last_result
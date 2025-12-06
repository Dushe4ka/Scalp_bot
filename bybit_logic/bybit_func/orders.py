from pybit.unified_trading import HTTP
from logger_config import setup_logger
from bybit_logic.bybit_func import calculator
from bybit_logic.bybit_func.market import get_qty_limits

logger = setup_logger(__name__)

def place_order(symbol, qty, side, order_type, session: HTTP):
    try:
        return session.place_order(
            category="linear",
            symbol=symbol.upper(),
            side=side,
            orderType=order_type,
            qty=qty
            )
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        return None

def place_limit_order(symbol, qty, side, price, session: HTTP):
    try:
        return session.place_order(
            category="linear",
            symbol=symbol.upper(),
            side=side,
            orderType="Limit",
            qty=qty,
            price=price
        )
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

def set_stop_loss(symbol, stop_loss_price, session: HTTP):
    try:
        return session.set_trading_stop(
            category="linear",
            symbol=symbol.upper(),
            stopLoss=str(stop_loss_price),
        )
    except Exception as e:
        logger.error(f"Error setting stop loss: {e}")
        return None

def place_n_limit_order(symbol, base_usdt_amount, side, base_price, session: HTTP, n: int, limit_percentage: float):
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
                result = place_limit_order(symbol, qty, side, limit_price, session)
                
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
from bybit_logic.bybit_func import session, position, market, calculator, orders
from pybit.unified_trading import WebSocket
from bybit_logic.config import DEMO_API_KEY, DEMO_API_SECRET, API_KEY, API_SECRET
from logger_config import setup_logger
import time

logger = setup_logger(__name__)

# ========== НАСТРОЙКИ ==========
SYMBOL = "KGENUSDT"  # Символ для торговли
USDT_AMOUNT = 100  # Сумма в USDT для открытия позиции
TRIGGER_PERCENTAGE = 2.0  # Процент изменения цены для срабатывания
POSITION_SIDE = "Buy"  # "Buy" для лонга, "Sell" для шорта
USE_DEMO = True  # Использовать demo счет
# ===============================

# Глобальные переменные для мониторинга
entry_price = None
position_qty = None  # ✨ НОВОЕ: Размер позиции
position_opened = False
trigger_called = False
current_price = None
price_change_percent = 0.0
pnl_usdt = 0.0  # ✨ НОВОЕ: PnL в USDT
last_log_time = 0  # ✨ НОВОЕ: Время последнего логирования


def price_trigger_callback():
    """
    Функция-заглушка, которая вызывается при достижении целевого процента изменения цены
    """
    global entry_price, current_price, price_change_percent, pnl_usdt
    
    logger.info("🚨 ЦЕНА ДОСТИГЛА ЦЕЛЕВОЙ ТОЧКИ! 🚨")
    print("=" * 50)
    print("🚨 СРАБАТЫВАНИЕ: Цена достигла целевого уровня!")
    print(f"Цена входа: {entry_price}")
    if current_price:
        print(f"Текущая цена: {current_price}")
    if price_change_percent:
        print(f"Изменение: {price_change_percent:.2f}%")
    if pnl_usdt:
        pnl_sign = "+" if pnl_usdt >= 0 else ""
        print(f"PnL: {pnl_sign}{pnl_usdt:.2f} USDT")
    print("=" * 50)
    # Здесь можно добавить логику установки стоп-лоссов, тейк-профитов и т.д.


def handle_ticker_price(message):
    """
    Обработчик сообщений от публичного WebSocket ticker stream
    Получает обновления цены в реальном времени
    """
    global entry_price, position_qty, position_opened, trigger_called, current_price, price_change_percent, pnl_usdt, last_log_time
    
    try:
        # Парсим сообщение от ticker stream
        if 'data' in message and message['data']:
            ticker_data = message['data']
            
            # Если данные в виде списка, берем первый элемент
            if isinstance(ticker_data, list):
                ticker_data = ticker_data[0]
            
            # Получаем текущую цену (lastPrice)
            current_price = float(ticker_data.get('lastPrice', 0))
            
            if current_price == 0 or entry_price is None or position_qty is None:
                return
            
            # Вычисляем изменение цены в процентах
            if POSITION_SIDE == "Buy":
                # Для лонга: считаем рост цены
                price_change_percent = ((current_price - entry_price) / entry_price) * 100
                # ✨ НОВОЕ: Рассчитываем PnL в USDT для лонга
                pnl_usdt = (current_price - entry_price) * position_qty
            else:
                # Для шорта: считаем падение цены
                price_change_percent = ((entry_price - current_price) / entry_price) * 100
                # ✨ НОВОЕ: Рассчитываем PnL в USDT для шорта
                pnl_usdt = (entry_price - current_price) * position_qty
            
            # Проверяем достижение целевого процента
            if price_change_percent >= TRIGGER_PERCENTAGE and not trigger_called:
                trigger_called = True
                price_trigger_callback()
            
            # ✨ ИСПРАВЛЕНИЕ: Логируем PnL только один раз каждые 10 секунд
            current_timestamp = int(time.time())
            if current_timestamp % 10 == 0 and current_timestamp != last_log_time:
                last_log_time = current_timestamp  # Сохраняем время последнего логирования
                pnl_sign = "+" if pnl_usdt >= 0 else ""
                pnl_emoji = "📈" if pnl_usdt >= 0 else "📉"
                logger.info(
                    f"{pnl_emoji} Цена: {current_price:.8g} | "
                    f"Изменение: {price_change_percent:+.2f}% | "
                    f"PnL: {pnl_sign}{pnl_usdt:.2f} USDT"
                )
                
    except Exception as e:
        logger.error(f"Ошибка обработки ticker: {e}")


def main():
    global entry_price, position_qty, position_opened
    
    logger.info("=" * 50)
    logger.info("Запуск мониторинга цены с автоматическим открытием позиции")
    logger.info(f"Символ: {SYMBOL}")
    logger.info(f"Сумма: {USDT_AMOUNT} USDT")
    logger.info(f"Сторона: {POSITION_SIDE}")
    logger.info(f"Целевой процент: {TRIGGER_PERCENTAGE}%")
    logger.info("=" * 50)
    
    # Создаем HTTP сессию
    http_session = session.create_session(use_demo=USE_DEMO)
    
    # Получаем текущую цену
    tickers = market.get_tickers_by_symbol(http_session, SYMBOL)
    current_market_price = float(tickers['result']['list'][0]['lastPrice'])
    logger.info(f"Текущая рыночная цена {SYMBOL}: {current_market_price}")
    
    # Рассчитываем количество для открытия позиции
    qty = calculator.calculate_qty(SYMBOL, USDT_AMOUNT, http_session)
    logger.info(f"Рассчитанное количество: {qty}")
    
    # Открываем позицию
    logger.info(f"Открываю {POSITION_SIDE} позицию на {qty} {SYMBOL}...")
    order_result = orders.place_order(SYMBOL, qty, POSITION_SIDE, "Market", http_session)
    
    if order_result and order_result.get('retCode') == 0:
        logger.info(f"✅ Позиция успешно открыта: {order_result}")
    else:
        logger.error(f"❌ Ошибка открытия позиции: {order_result}")
        return
    
    # Получаем цену входа и размер позиции (среднюю цену позиции)
    time.sleep(1)  # Небольшая задержка для обновления позиции
    position_data = position.get_positions_by_symbol(http_session, SYMBOL)
    
    if position_data and position_data.get('result', {}).get('list'):
        position_info = position_data['result']['list'][0]
        entry_price = float(position_info['avgPrice'])
        position_qty = float(position_info['size'])  # ✨ НОВОЕ: Получаем размер позиции
        logger.info(f"✅ Цена входа (avgPrice): {entry_price}")
        logger.info(f"✅ Размер позиции (size): {position_qty}")
    else:
        logger.error("❌ Не удалось получить данные позиции")
        return
    
    # ✨ ИСПРАВЛЕНИЕ: Используем публичный WebSocket для мониторинга цены
    logger.info("🔌 Подключаюсь к публичному WebSocket для мониторинга цены...")
    
    try:
        # Публичный WebSocket (как в примерах и ex_old.py)
        # НЕ требует API ключи и параметр demo
        ws = WebSocket(
            channel_type="linear",  # Публичный канал
            testnet=False
        )
        
        # Подписываемся на ticker stream для получения цены
        ws.ticker_stream(SYMBOL, handle_ticker_price)
        
        logger.info(f"✅ Подписка на {SYMBOL} ticker stream активна")
        logger.info(f"⏳ Ожидание изменения цены на {TRIGGER_PERCENTAGE}%...")
        logger.info("📊 PnL будет выводиться каждые 10 секунд")
        logger.info("Нажмите Ctrl+C для остановки")
        
        # Держим соединение открытым (как в примерах)
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\n⏹ Остановка мониторинга...")
        if 'ws' in locals():
            ws.exit()
    except Exception as e:
        logger.error(f"❌ Ошибка в WebSocket соединении: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()


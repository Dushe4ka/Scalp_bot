"""
Скрипт для автоматического открытия позиции и мониторинга цены через WebSocket
При достижении целевого процента изменения цены вызывается функция-заглушка
"""
from bybit_logic.bybit_func import session, position, market, calculator, orders
from bybit_logic.bybit_func.price_stream import PriceStream  # ✨ НОВОЕ: Импортируем модуль для WebSocket
from logger_config import setup_logger
import time
import os
import dotenv

dotenv.load_dotenv()

logger = setup_logger(__name__)

# ============================================
SYMBOL = os.getenv("SYMBOL").upper()
USDT_AMOUNT = float(os.getenv("USDT_AMOUNT"))
TRIGGER_PERCENTAGE = float(os.getenv("TRIGGER_PERCENTAGE"))
STOP_LOSS_PERCENTAGE = float(os.getenv("STOP_LOSS_PERCENTAGE"))
CORRECTION_SL_PERCENTAGE = float(os.getenv("CORRECTION_SL_PERCENTAGE"))
POSITION_SIDE = os.getenv("POSITION_SIDE")
USE_DEMO = bool(os.getenv("USE_DEMO"))
PNL_LOG_INTERVAL = float(os.getenv("PNL_LOG_INTERVAL"))
# ============================================

# Переменные для хранения данных о позиции
entry_price = None  # Цена, по которой была открыта позиция
position_qty = None  # Количество монет в позиции
position_opened = False  # Открыта ли позиция
trigger_called = False  # Сработал ли триггер (достигнут целевой процент)
current_price = None  # Текущая рыночная цена
price_change_percent = 0.0  # На сколько процентов изменилась цена от входа
pnl_usdt = 0.0  # Текущая прибыль/убыток в USDT (PnL = Profit and Loss)
last_log_time = 0  # Время последнего вывода PnL в лог (чтобы не дублировать)
http_session = None


def price_trigger_callback():
    """
    Эта функция вызывается, когда цена изменилась на целевой процент
    
    Что такое целевой процент?
    - Если вы купили (Buy) и цена выросла на TRIGGER_PERCENTAGE% - срабатывает
    - Если вы продали (Sell) и цена упала на TRIGGER_PERCENTAGE% - срабатывает
    
    Здесь можно добавить свою логику:
    - Установить стоп-лосс
    - Установить тейк-профит
    - Закрыть позицию
    - Отправить уведомление
    """
    global entry_price, current_price, price_change_percent, pnl_usdt, http_session
    
    logger.info("🚨 ЦЕНА ДОСТИГЛА ЦЕЛЕВОГО УРОВНЯ! 🚨")
    print("=" * 50)
    print("🚨 СРАБАТЫВАНИЕ: Цена достигла целевого уровня!")
    print(f"Цена входа: {entry_price}")
    
    if current_price:
        print(f"Текущая цена: {current_price}")
    
    if price_change_percent:
        print(f"Изменение цены: {price_change_percent:.2f}%")
    
    if pnl_usdt:
        # Показываем знак "+" для прибыли
        pnl_sign = "+" if pnl_usdt >= 0 else ""
        print(f"Прибыль/убыток (PnL): {pnl_sign}{pnl_usdt:.2f} USDT")

    try:
        orders.set_stop_loss(SYMBOL, current_price, http_session)
        print(f"✅ Без убыток (БУ) успешно установлен на {current_price}")
        
    except Exception as e:
        print(f"❌ Ошибка установки без убытка (БУ) для цены {current_price}: {e}")
        
        # Пытаемся установить альтернативный БУ только если первый не удался
        try:
            calc_current_price = calculator.calculate_little_less_price(current_price, CORRECTION_SL_PERCENTAGE, POSITION_SIDE)
            orders.set_stop_loss(SYMBOL, calc_current_price, http_session)
            print(f"✅ Альтернативный без убыток (БУ) успешно установлен на {calc_current_price}")
            
        except Exception as e2:
            print(f"❌ Ошибка установки альтернативного без убытка (БУ) для цены {calc_current_price}: {e2}")
            print("⚠️ Оба варианта установки БУ завершились ошибкой")
            
    print("=" * 50)

def handle_ticker_price(message):
    """
    Эта функция вызывается каждый раз, когда приходит обновление цены от WebSocket
    
    Что она делает:
    1. Получает текущую цену из сообщения
    2. Считает, на сколько процентов изменилась цена от входа
    3. Считает текущую прибыль/убыток (PnL) в USDT
    4. Проверяет, достигнута ли целевая цена
    5. Выводит информацию в лог каждые N секунд
    """
    global entry_price, position_qty, position_opened, trigger_called
    global current_price, price_change_percent, pnl_usdt, last_log_time
    
    try:
        # Проверяем, есть ли данные в сообщении
        if 'data' not in message or not message['data']:
            return
        
        # Получаем данные о цене
        ticker_data = message['data']
        
        # Если данные пришли в виде списка, берем первый элемент
        if isinstance(ticker_data, list):
            ticker_data = ticker_data[0]
        
        # Извлекаем текущую цену из данных
        current_price = float(ticker_data.get('lastPrice', 0))
        
        # Проверяем, что у нас есть все необходимые данные
        if current_price == 0:
            return  # Цена не получена
        
        if entry_price is None:
            return  # Цена входа еще не известна
        
        if position_qty is None:
            return  # Размер позиции еще не известен
        
        # ============================================
        # РАСЧЕТ ИЗМЕНЕНИЯ ЦЕНЫ В ПРОЦЕНТАХ
        # ============================================
        if POSITION_SIDE == "Buy":
            # Для покупки (лонг): прибыль = рост цены
            # Формула: (текущая_цена - цена_входа) / цена_входа * 100
            price_change_percent = ((current_price - entry_price) / entry_price) * 100
            
            # Рассчитываем прибыль/убыток в USDT
            # Формула: (текущая_цена - цена_входа) * количество_монет
            pnl_usdt = (current_price - entry_price) * position_qty
            
        else:  # POSITION_SIDE == "Sell"
            # Для продажи (шорт): прибыль = падение цены
            # Формула: (цена_входа - текущая_цена) / цена_входа * 100
            price_change_percent = ((entry_price - current_price) / entry_price) * 100
            
            # Рассчитываем прибыль/убыток в USDT
            # Формула: (цена_входа - текущая_цена) * количество_монет
            pnl_usdt = (entry_price - current_price) * position_qty
        
        # ============================================
        # ПРОВЕРКА: ДОСТИГНУТА ЛИ ЦЕЛЕВАЯ ЦЕНА?
        # ============================================
        if price_change_percent >= TRIGGER_PERCENTAGE and not trigger_called:
            # Целевой процент достигнут, и функция еще не вызывалась
            trigger_called = True
            price_trigger_callback()
        
        # ============================================
        # ВЫВОД ИНФОРМАЦИИ В ЛОГ ПЕРИОДИЧЕСКИ
        # ============================================
        # Получаем текущее время в секундах
        current_timestamp = int(time.time())
        
        # Логируем только один раз каждые N секунд (чтобы не засорять логи)
        # Проверяем: прошло ли N секунд с последнего логирования?
        if (current_timestamp % PNL_LOG_INTERVAL == 0 and 
            current_timestamp != last_log_time):
            
            # Сохраняем время последнего логирования
            last_log_time = current_timestamp
            
            # Определяем знак для PnL (плюс для прибыли, минус для убытка)
            pnl_sign = "+" if pnl_usdt >= 0 else ""
            
            # Выбираем эмодзи: 📈 для прибыли, 📉 для убытка
            pnl_emoji = "📈" if pnl_usdt >= 0 else "📉"
            
            # Выводим информацию в лог
            logger.info(
                f"{pnl_emoji} Цена: {current_price:.8g} | "
                f"Изменение: {price_change_percent:+.2f}% | "
                f"PnL: {pnl_sign}{pnl_usdt:.2f} USDT"
            )
                
    except Exception as e:
        logger.error(f"Ошибка при обработке обновления цены: {e}")


def main():
    """
    Главная функция - выполняет всю работу:
    1. Открывает позицию
    2. Подключается к WebSocket для мониторинга цены
    3. Следит за изменением цены в реальном времени
    """
    global entry_price, position_qty, position_opened
    
    # ============================================
    # ШАГ 1: ВЫВОД НАЧАЛЬНОЙ ИНФОРМАЦИИ
    # ============================================
    logger.info("=" * 50)
    logger.info("🚀 Запуск мониторинга цены с автоматическим открытием позиции")
    logger.info("=" * 50)
    logger.info(f"📊 Символ: {SYMBOL}")
    logger.info(f"💰 Сумма: {USDT_AMOUNT} USDT")
    logger.info(f"📈 Сторона: {POSITION_SIDE} ({'Покупка' if POSITION_SIDE == 'Buy' else 'Продажа'})")
    logger.info(f"🎯 Целевой процент: {TRIGGER_PERCENTAGE}%")
    logger.info(f"⏱️  Интервал логирования PnL: {PNL_LOG_INTERVAL} секунд")
    logger.info("=" * 50)
    
    # ============================================
    # ШАГ 2: ПОДКЛЮЧЕНИЕ К БИРЖЕ
    # ============================================
    logger.info("🔌 Подключаюсь к бирже Bybit...")
    global http_session
    http_session = session.create_session(use_demo=USE_DEMO)
    logger.info("✅ Подключение установлено")
    
    # ============================================
    # ШАГ 3: ПОЛУЧЕНИЕ ТЕКУЩЕЙ ЦЕНЫ
    # ============================================
    logger.info(f"📊 Получаю текущую цену {SYMBOL}...")
    tickers = market.get_tickers_by_symbol(http_session, SYMBOL)
    current_market_price = float(tickers['result']['list'][0]['lastPrice'])
    logger.info(f"✅ Текущая рыночная цена: {current_market_price}")
    
    # ============================================
    # ШАГ 4: РАСЧЕТ КОЛИЧЕСТВА МОНЕТ
    # ============================================
    logger.info(f"🧮 Рассчитываю количество монет для суммы {USDT_AMOUNT} USDT...")
    qty = calculator.calculate_qty(SYMBOL, USDT_AMOUNT, http_session)
    logger.info(f"✅ Рассчитанное количество: {qty} {SYMBOL}")
    
    # ============================================
    # ШАГ 5.1: ОТКРЫТИЕ ПОЗИЦИИ
    # ============================================
    logger.info(f"📝 Открываю {POSITION_SIDE} позицию на {qty} {SYMBOL}...")
    order_result = orders.place_order(SYMBOL, qty, POSITION_SIDE, "Market", http_session)
    
    if order_result and order_result.get('retCode') == 0:
        logger.info(f"✅ Позиция успешно открыта!")
        logger.info(f"   ID ордера: {order_result.get('result', {}).get('orderId', 'N/A')}")
    else:
        error_msg = order_result.get('retMsg', 'Неизвестная ошибка') if order_result else 'Нет ответа от сервера'
        logger.error(f"❌ Ошибка открытия позиции: {error_msg}")
        return
    
    # ============================================
    # ШАГ 6.1: ПОЛУЧЕНИЕ ДАННЫХ О ПОЗИЦИИ
    # ============================================
    logger.info("⏳ Жду обновления данных о позиции...")
    time.sleep(1)  # Ждем 1 секунду, чтобы биржа обновила данные
    
    logger.info("📊 Получаю данные о позиции...")
    position_data = position.get_positions_by_symbol(http_session, SYMBOL)
    
    if position_data and position_data.get('result', {}).get('list'):
        # Извлекаем информацию о позиции
        position_info = position_data['result']['list'][0]
        entry_price = float(position_info['avgPrice'])  # Средняя цена входа
        position_qty = float(position_info['size'])  # Размер позиции
        
        logger.info(f"✅ Цена входа: {entry_price}")
        logger.info(f"✅ Размер позиции: {position_qty} {SYMBOL}")
    else:
        logger.error("❌ Не удалось получить данные о позиции")
        logger.error("   Возможно, позиция еще не обновилась. Попробуйте запустить снова.")
        return

    # ============================================
    # ШАГ 6.2: УСТАНОВКА СТОП-ЛОССА
    # ============================================
    logger.info(f"📝 Устанавливаю стоп-лосс на {SYMBOL}...")
    stop_loss_price = calculator.calculate_stop_loss(entry_price, STOP_LOSS_PERCENTAGE, POSITION_SIDE)
    logger.info(f"✅ Стоп-лосс установлен на {stop_loss_price}")
    try:
        orders.set_stop_loss(SYMBOL, stop_loss_price, http_session)
        logger.info(f"✅ Стоп-лосс успешно установлен")
    except Exception as e:
        logger.error(f"❌ Ошибка установки стоп-лосса: {e}")
        return
    
    # ============================================
    # ШАГ 7: ПОДКЛЮЧЕНИЕ К WEBSOCKET ДЛЯ МОНИТОРИНГА
    # ============================================
    logger.info("=" * 50)
    logger.info("🔌 Подключаюсь к WebSocket для мониторинга цены в реальном времени...")
    logger.info("=" * 50)
    
    # ✨ УПРОЩЕННЫЙ КОД: Используем новый модуль PriceStream
    price_stream = PriceStream(
        symbol=SYMBOL,
        price_handler=handle_ticker_price,
        testnet=False
    )
    
    logger.info(f"⏳ Ожидание изменения цены на {TRIGGER_PERCENTAGE}%...")
    logger.info(f"📊 PnL будет выводиться каждые {PNL_LOG_INTERVAL} секунд")
    logger.info("")
    logger.info("💡 Нажмите Ctrl+C для остановки")
    logger.info("=" * 50)
    
    # Запускаем мониторинг (автоматически обрабатывает Ctrl+C)
    price_stream.run_forever()


if __name__ == "__main__":
    main()


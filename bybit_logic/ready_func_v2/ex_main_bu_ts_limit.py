"""
Скрипт для автоматического открытия позиции и мониторинга цены через WebSocket
При достижении целевого процента изменения цены вызывается функция-обработчик
"""
from bybit_logic.bybit_func import session, position, market, calculator, orders, stop_trade
from bybit_logic.bybit_func.price_stream import PriceStream
from bybit_logic.bybit_func.trailing_stop import TrailingStop
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
TRIGGER_TS_PERCENTAGE = float(os.getenv("TRIGGER_TS_PERCENTAGE"))
STOP_LOSS_PERCENTAGE = float(os.getenv("STOP_LOSS_PERCENTAGE"))
CORRECTION_SL_PERCENTAGE = float(os.getenv("CORRECTION_SL_PERCENTAGE"))
POSITION_SIDE = os.getenv("POSITION_SIDE")
USE_DEMO = bool(os.getenv("USE_DEMO"))
COUNT_LIMIT_ORDERS = int(os.getenv("COUNT_LIMIT_ORDERS"))
LIMIT_PERCENTAGE = float(os.getenv("LIMIT_PERCENTAGE"))
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
trailing_stop = None
previous_avg_price = None  # предыдущая средняя цена (для отслеживания)
previous_position_size = None  # предыдущий размер позиции
last_position_check_time = 0  # Время последней проверки позиции (в секундах)
price_stream = None  # Объект для работы с WebSocket

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
    global entry_price, current_price, price_change_percent, pnl_usdt, http_session, trailing_stop
    
    logger.info("🚨 ЦЕНА ДОСТИГЛА ЦЕЛЕВОГО УРОВНЯ! Устанавливаю БУ и активирую трейлинг стоп! 🚨")
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

    # ============================================
    # УСТАНОВКА БУ (безубыток) на текущей цене с отступом
    # ============================================
    # Рассчитываем цену БУ с использованием calculator.calculate_little_less_price()
    breakeven_price = calculator.calculate_little_less_price(current_price, CORRECTION_SL_PERCENTAGE, POSITION_SIDE)
    
    logger.info(f"📝 Устанавливаю БУ на {breakeven_price:.8g} (текущая цена: {current_price:.8g}, отступ: {CORRECTION_SL_PERCENTAGE}%)")
    
    # Устанавливаем БУ и проверяем результат
    result = orders.set_stop_loss(SYMBOL, current_price, http_session)
    
    bu_success = False  # Флаг успешной установки БУ
    
    if result and result.get('retCode') == 0:
        logger.info(f"✅ БУ (безубыток) успешно установлен на {current_price:.8g}")
        print(f"✅ БУ установлен на {current_price:.8g}")
        bu_success = True
    else:
        error_msg = result.get('retMsg', 'Неизвестная ошибка') if result else 'Нет ответа от сервера'
        logger.error(f"❌ Ошибка установки БУ: {error_msg}")
        print(f"❌ Ошибка установки БУ: {error_msg}")
        
        # Пытаемся установить альтернативный БУ с большим отступом

        logger.info(f"📝 Пытаюсь установить альтернативный БУ на {breakeven_price:.8g}...")
        result2 = orders.set_stop_loss(SYMBOL, breakeven_price, http_session)
        
        if result2 and result2.get('retCode') == 0:
            logger.info(f"✅ Альтернативный БУ успешно установлен на {breakeven_price:.8g}")
            print(f"✅ Альтернативный БУ установлен на {breakeven_price:.8g}")
            bu_success = True
        else:
            error_msg2 = result2.get('retMsg', 'Неизвестная ошибка') if result2 else 'Нет ответа'
            logger.error(f"❌ Ошибка установки альтернативного БУ: {error_msg2}")
            print(f"❌ Ошибка установки альтернативного БУ: {error_msg2}")

    # ============================================
    # АКТИВАЦИЯ ТРЕЙЛИНГ СТОПА (ТОЛЬКО ЕСЛИ БУ УСПЕШНО УСТАНОВЛЕН)
    # ============================================
    if bu_success:
        if trailing_stop is not None:
            trailing_stop.activate(current_price)  # Активируем трейлинг стоп на текущей цене
            logger.info(f"🟢 Трейлинг стоп активирован на цене {current_price:.8g}")
            print(f"🟢 Трейлинг стоп активирован!")
        else:
            logger.error("❌ Объект трейлинг стопа не создан!")
            print("❌ Ошибка: трейлинг стоп не создан!")
    else:
        logger.warning("⚠️ Трейлинг стоп НЕ активирован, так как БУ не был установлен!")
        print("⚠️ Трейлинг стоп НЕ активирован, так как БУ не был установлен!")
    
    print("=" * 50)

def check_and_update_position(check_interval: float = 1.0) -> bool:
    """
    Проверяет и обновляет данные о позиции с кешированием по времени
    
    Args:
        check_interval: Интервал проверки в секундах (по умолчанию 1.0 секунда)
    
    Returns:
        bool: True если позиция изменилась, False в противном случае
        
    Пример:
        # Проверка раз в секунду
        if check_and_update_position(check_interval=1.0):
            logger.info("Позиция изменилась!")
        
        # Проверка раз в 5 секунд
        if check_and_update_position(check_interval=5.0):
            logger.info("Позиция изменилась!")
    """
    global entry_price, position_qty, previous_avg_price, previous_position_size
    global last_position_check_time, http_session, SYMBOL
    
    current_timestamp = time.time()
    
    # ✅ КЕШИРОВАНИЕ: Проверяем позицию только если прошло достаточно времени
    if current_timestamp - last_position_check_time < check_interval:
        return False  # Пропускаем проверку - еще не прошло достаточно времени
    
    last_position_check_time = current_timestamp
    
    try:
        # Получаем данные о позиции с биржи
        position_data = position.get_positions_by_symbol(http_session, SYMBOL)
        
        if not position_data or not position_data.get('result', {}).get('list'):
            return False
        
        position_info = position_data['result']['list'][0]
        current_size = float(position_info.get('size', 0))
        current_avg_price = float(position_info.get('avgPrice', 0))
        
        # Если позиция закрыта (size = 0), ничего не делаем
        if current_size == 0:
            logger.info(f"🔄 Позиция закрыта, размер: {current_size:.8g}")
            logger.info(f"Останавливаем мониторинг и торговлю")
            stop_trade.stop_trading_by_symbol(SYMBOL, http_session)
            price_stream.stop()
            return False
        
        # Первая инициализация
        if previous_avg_price is None or entry_price is None:
            previous_avg_price = current_avg_price
            previous_position_size = current_size
            entry_price = current_avg_price
            position_qty = current_size
            logger.debug(f"📍 Инициализация позиции: avgPrice={current_avg_price:.8g}, size={current_size:.8g}")
            return False
        
        # Проверяем изменения (с учетом погрешности float)
        price_changed = abs(current_avg_price - previous_avg_price) > 0.00000001
        size_changed = abs(current_size - previous_position_size) > 0.00000001
        
        if price_changed or size_changed:
            logger.info(f"🔄 Обнаружено изменение позиции:")
            logger.info(f"   avgPrice: {previous_avg_price:.8g} → {current_avg_price:.8g}")
            logger.info(f"   size: {previous_position_size:.8g} → {current_size:.8g}")
            
            # Сохраняем предыдущие значения для логирования
            old_entry_price = entry_price
            old_position_qty = position_qty
            
            # Обновляем глобальные переменные
            entry_price = current_avg_price
            position_qty = current_size
            previous_avg_price = current_avg_price
            previous_position_size = current_size
            
            logger.info(f"✅ Позиция обновлена: entry_price={entry_price:.8g}, position_qty={position_qty:.8g}")
            
            return True  # Позиция изменилась
        
        return False  # Изменений нет
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке позиции: {e}")
        return False

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
    global previous_avg_price, previous_position_size, http_session

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

        # Проверяем позицию раз в секунду
        position_changed = check_and_update_position(check_interval=1.0)

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
        # ОБНОВЛЕНИЕ ТРЕЙЛИНГ СТОПА (если он активен)
        # ============================================
        if trailing_stop is not None and trailing_stop.is_active:
            # Обновляем трейлинг стоп при каждом получении новой цены
            if trailing_stop.update(current_price):
                # Стоп-лосс был обновлен
                status = trailing_stop.get_status()
                logger.info(
                    f"📈 Трейлинг стоп обновлен! "
                    f"Стоп: {status['last_stop_price']:.8g}, "
                    f"Цена: {current_price:.8g}"
                )

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
    global entry_price, position_qty, position_opened, http_session, price_stream
    global previous_avg_price, previous_position_size, last_position_check_time
    
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
    # ШАГ 2: ПОДКЛЮЧЕНИЕ К БИРЖЕ И СОЗДАНИЕ ОБЪЕКТА ТРЕЙЛИНГ СТОПА
    # ============================================
    logger.info("🔌 Подключаюсь к бирже Bybit...")
    http_session = session.create_session(use_demo=USE_DEMO)
    logger.info("✅ Подключение установлено")

    global trailing_stop  # Объявляем, что используем глобальную переменную

    trailing_stop = TrailingStop(
        symbol=SYMBOL,
        session=http_session,
        trigger_percentage=TRIGGER_TS_PERCENTAGE,  # Обновлять каждые TRIGGER_TS_PERCENTAGE%
        position_side=POSITION_SIDE,
        offset_percentage=0.1  # Отступ 0.1% для защиты от проскальзывания
    )

    logger.info(f"📊 Трейлинг стоп создан (шаг: {TRIGGER_TS_PERCENTAGE}%)")
        
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
    
    # ✅ Инициализируем переменные для отслеживания изменений
    previous_avg_price = entry_price
    previous_position_size = position_qty
    last_position_check_time = time.time()  # Инициализируем время последней проверки позиции
    
    # ============================================
    # ШАГ 6.2: УСТАНОВКА СТОП-ЛОССА И ЛИМИТНЫХ ОРДЕРОВ
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

    logger.info(f"📝 Устанавливаю {COUNT_LIMIT_ORDERS} лимитных ордеров на {SYMBOL}...")
    place_n_limit_order = orders.place_n_limit_order(SYMBOL, USDT_AMOUNT, POSITION_SIDE, entry_price, http_session, COUNT_LIMIT_ORDERS, LIMIT_PERCENTAGE)

    # ✅ ПРАВИЛЬНАЯ ПРОВЕРКА: place_n_limit_order - это СПИСОК!
    if place_n_limit_order is None:
        logger.error(f"❌ Критическая ошибка при размещении лимитных ордеров")
    elif not place_n_limit_order:  # Пустой список
        logger.error(f"❌ Не удалось разместить ни одного лимитного ордера")
    else:
        # Проверяем результаты: считаем успешные и неуспешные
        successful_orders = [r for r in place_n_limit_order if r.get('success', False)]
        failed_orders = [r for r in place_n_limit_order if not r.get('success', False)]
        
        if failed_orders:
            logger.warning(f"⚠️ Размещено {len(successful_orders)}/{COUNT_LIMIT_ORDERS} ордеров")
            for failed in failed_orders:
                logger.error(f"   ❌ Ордер #{failed.get('order_number')}: {failed.get('error', 'Unknown error')}")
        else:
            logger.info(f"✅ Все {COUNT_LIMIT_ORDERS} лимитных ордеров успешно установлены")
            
    # ============================================
    # ШАГ 7: ПОДКЛЮЧЕНИЕ К WEBSOCKET ДЛЯ МОНИТОРИНГА
    # ============================================
    logger.info("=" * 50)
    logger.info("🔌 Подключаюсь к WebSocket для мониторинга цены в реальном времени...")
    logger.info("=" * 50)
    
    # Используем модуль PriceStream для мониторинга цены
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


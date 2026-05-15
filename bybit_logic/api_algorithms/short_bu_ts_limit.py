"""
Скрипт для автоматического открытия позиции и мониторинга цены через WebSocket
При достижении целевого процента изменения цены вызывается функция-обработчик
"""
from bybit_logic.bybit_func import session, position, market, calculator, orders, stop_trade
from bybit_logic.bybit_func.price_stream import PriceStream
from bybit_logic.bybit_func.trailing_stop import TrailingStop
from celery_app.tasks.notifications import send_notification_task
from logger_config import setup_logger
import time
import os
import dotenv
from config import TRADING_MARGIN_MODE, USE_DEMO as USE_DEMO_FROM_ENV

dotenv.load_dotenv()

logger = setup_logger(__name__)

# ============================================
# SYMBOL = os.getenv("SYMBOL").upper()
# Сумма из .env — как для пользователя в логах/Telegram; для расчёта qty и лимитов — ×10 (см. short_bu_ts_limit_multiuser).
USDT_AMOUNT = float(os.getenv("SHORT_BU_TS_LIMIT_USDT_AMOUNT", os.getenv("USDT_AMOUNT")))
ALGORITHMS_SUM_FOR_TRADES = USDT_AMOUNT * 10
TRIGGER_PERCENTAGE = float(os.getenv("TRIGGER_PERCENTAGE"))
TRIGGER_TS_PERCENTAGE = float(os.getenv("TRIGGER_TS_PERCENTAGE"))
STOP_LOSS_PERCENTAGE = float(os.getenv("STOP_LOSS_PERCENTAGE"))
CORRECTION_SL_PERCENTAGE = float(os.getenv("CORRECTION_SL_PERCENTAGE"))
POSITION_SIDE = os.getenv("POSITION_SIDE")
# По умолчанию из .env (config.USE_DEMO); в start_trading() можно передать use_demo явно.
USE_DEMO = USE_DEMO_FROM_ENV
LEVERAGE = 10
COUNT_LIMIT_ORDERS = int(os.getenv("COUNT_LIMIT_ORDERS"))
LIMIT_PERCENTAGE = float(os.getenv("LIMIT_PERCENTAGE"))
PNL_LOG_INTERVAL = float(os.getenv("PNL_LOG_INTERVAL"))
# ============================================

# Переменные для хранения данных о позиции
SYMBOL = None
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
should_stop = False  # ✅ Флаг для остановки алгоритма
# Уведомление о финале: True после рассылки о закрытии позиции или общего финала
completion_notified = False
monitoring_active = False  # True после успешного входа, перед run_forever WebSocket
averaging_fills_count = 0  # Количество сработавших усреднений (по факту роста размера позиции)
# Linear UTA hedge: 1=нога Buy, 2=Sell; None = one-way.
ACTIVE_POSITION_IDX = None


def _hedge_leg_position_idx(side: str | None) -> int:
    return 1 if (side or "").strip() == "Buy" else 2


def get_active_bu_trigger_percentage() -> float:
    """
    После 3-го усреднения БУ должен срабатывать на 1%.
    До этого используется базовый TRIGGER_PERCENTAGE из .env.
    """
    if averaging_fills_count >= 3:
        return 1.0
    return TRIGGER_PERCENTAGE


def get_active_initial_ts_trigger_percentage() -> float:
    """
    Порог для немедленной установки первого трейлинг-стопа после активации БУ:
    как и раньше, это BU + 1%.
    """
    return get_active_bu_trigger_percentage() + 1.0

def price_trigger_callback(active_bu_trigger: float) -> bool:
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
    global entry_price, current_price, price_change_percent, pnl_usdt, http_session, trailing_stop, SYMBOL
    global ACTIVE_POSITION_IDX

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
    # УСТАНОВКА БУ (безубыток): централизованно через orders
    # ============================================
    bu_success, bu_price, _ = orders.set_stop_loss_with_breakeven_retries(
        SYMBOL,
        current_price,
        http_session,
        POSITION_SIDE,
        correction_percent_start=CORRECTION_SL_PERCENTAGE,
        correction_percent_stop=2.0,
        correction_percent_step=0.5,
        position_idx=ACTIVE_POSITION_IDX,
    )
    if bu_success and bu_price is not None:
        logger.info(f"✅ БУ (безубыток) успешно установлен на {bu_price:.8g}")
        print(f"✅ БУ установлен на {bu_price:.8g}")
    else:
        logger.error("❌ Не удалось установить БУ после всех попыток")
        print("❌ Не удалось установить БУ после всех попыток")
        return False

    # ============================================
    # АКТИВАЦИЯ ТРЕЙЛИНГ СТОПА (ТОЛЬКО ЕСЛИ БУ УСПЕШНО УСТАНОВЛЕН)
    # ============================================
    if trailing_stop is None:
        logger.error("❌ Объект трейлинг стопа не создан!")
        print("❌ Ошибка: трейлинг стоп не создан!")
        return True

    trailing_stop.activate(current_price)  # Активируем трейлинг стоп на текущей цене
    logger.info(f"🟢 Трейлинг стоп активирован на цене {current_price:.8g} (БУ установлен)")
    print("🟢 Трейлинг стоп активирован!")

    # КРИТИЧНО: Если прибыль уже больше активного порога initial TS,
    # сразу устанавливаем первый стоп трейлинг стопа на текущей прибыли
    # Это нужно, чтобы зафиксировать прибыль сразу, а не ждать дальнейшего роста
    active_initial_ts_trigger = get_active_initial_ts_trigger_percentage()
    if price_change_percent >= active_initial_ts_trigger:
        logger.info(
            f"💰 Прибыль уже {price_change_percent:.2f}% "
            f"(больше целевого порога {active_initial_ts_trigger:.2f}%)"
        )
        logger.info(f"📝 Сразу устанавливаю первый стоп трейлинг стопа на текущей цене...")
        if trailing_stop.set_initial_stop(current_price):
            logger.info(f"✅ Первый стоп трейлинг стопа установлен сразу на текущей прибыли {price_change_percent:.2f}%")
            print("✅ Первый стоп трейлинг стопа установлен!")
        else:
            logger.warning("⚠️ Не удалось установить начальный стоп, он установится при следующем росте")
    else:
            logger.info(
                f"ℹ️ Первый стоп трейлинг стопа установится при росте цены на "
                f"{trailing_stop.trigger_percentage}% после БУ ({active_bu_trigger:.2f}%)"
            )

    print("=" * 50)
    return True

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
    global last_position_check_time, http_session, SYMBOL, should_stop
    global completion_notified
    global averaging_fills_count
    
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
            if price_stream:
                price_stream.stop()
            should_stop = True  # ✅ Устанавливаем флаг остановки

            # Данные с биржи (get_closed_pnl), как POST /result_position_info_by_symbol
            exchange_report = position.result_position_info(SYMBOL, http_session)
            if not exchange_report:
                exchange_report = "❌ Позиция не найдена"
            notification_text = f"🔄 Позиция закрыта\n\n{exchange_report}"
            send_notification_task.delay(notification_text)
            completion_notified = True
            logger.info(f"✅ Уведомление отправлено подписчикам о закрытии позиции")

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

            # Фиксируем сработавшее усреднение по факту увеличения размера позиции.
            # Уменьшение размера (частичное закрытие) не учитываем.
            if current_size > previous_position_size + 1e-8:
                averaging_fills_count += 1
                logger.info(f"📌 Усреднение #{averaging_fills_count} зафиксировано (size вырос)")
            
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
        active_bu_trigger = get_active_bu_trigger_percentage()
        if price_change_percent >= active_bu_trigger and not trigger_called:
            # Целевой процент достигнут, пробуем поставить БУ.
            # trigger_called станет True только при успешной установке БУ.
            if price_trigger_callback(active_bu_trigger):
                trigger_called = True
        
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


def _resolve_use_demo(use_demo: bool | None) -> bool:
    """Явный аргумент start_trading имеет приоритет над USE_DEMO из .env."""
    if use_demo is not None:
        return bool(use_demo)
    return bool(USE_DEMO_FROM_ENV)


def start_trading(symbol: str, *, use_demo: bool | None = None):
    """
    Главная функция - выполняет всю работу:
    1. Открывает позицию
    2. Подключается к WebSocket для мониторинга цены
    3. Следит за изменением цены в реальном времени

    Args:
        symbol: торговая пара
        use_demo: True/False — demo Bybit (DEMO_API_*); None — взять из .env (USE_DEMO)
    """
    effective_use_demo = _resolve_use_demo(use_demo)
    global entry_price, position_qty, position_opened, http_session, price_stream
    global previous_avg_price, previous_position_size, last_position_check_time
    global SYMBOL, should_stop, trigger_called, current_price, price_change_percent
    global pnl_usdt, last_log_time, trailing_stop
    global completion_notified, monitoring_active
    global averaging_fills_count
    global ACTIVE_POSITION_IDX

    # Сбрасываем все переменные состояния
    ACTIVE_POSITION_IDX = None
    SYMBOL = None
    entry_price = None
    position_qty = None
    position_opened = False
    trigger_called = False  
    current_price = None
    price_change_percent = 0.0
    pnl_usdt = 0.0
    last_log_time = 0
    http_session = None
    trailing_stop = None
    previous_avg_price = None
    previous_position_size = None
    last_position_check_time = 0
    price_stream = None
    should_stop = False
    completion_notified = False
    monitoring_active = False
    averaging_fills_count = 0

    SYMBOL = symbol.upper()
    
    # ============================================
    # ШАГ 1: ВЫВОД НАЧАЛЬНОЙ ИНФОРМАЦИИ
    # ============================================
    logger.info("=" * 50)
    logger.info("🚀 Запуск мониторинга цены с автоматическим открытием позиции")
    logger.info("=" * 50)
    logger.info(f"📊 Символ: {SYMBOL}")
    logger.info(f"🔑 Режим API: {'demo' if effective_use_demo else 'mainnet'} (use_demo={effective_use_demo})")
    logger.info(f"💰 Сумма: {USDT_AMOUNT} USDT")
    logger.info(f"📈 Сторона: {POSITION_SIDE} ({'Покупка' if POSITION_SIDE == 'Buy' else 'Продажа'})")
    logger.info(
        f"🎯 Целевой процент БУ: {TRIGGER_PERCENTAGE}% "
        f"(после 3 усреднений автоматически 1.0%)"
    )
    logger.info(f"⏱️  Интервал логирования PnL: {PNL_LOG_INTERVAL} секунд")
    logger.info("=" * 50)
    
    # ============================================
    # ШАГ 2: ПОДКЛЮЧЕНИЕ К БИРЖЕ 
    # ============================================
    logger.info("🔌 Подключаюсь к бирже Bybit...")
    http_session = session.create_session(use_demo=effective_use_demo)
    logger.info("✅ Подключение установлено")

    logger.info(f"⚙️ Устанавливаю режим маржи аккаунта: {TRADING_MARGIN_MODE}...")
    try:
        position.set_account_margin_mode(http_session, SYMBOL, desired_mode=TRADING_MARGIN_MODE)
    except Exception as e:
        logger.error(f"❌ Не удалось установить режим маржи {TRADING_MARGIN_MODE}: {e}")
        return

    logger.info(f"⚙️ Устанавливаю кредитное плечо {LEVERAGE}x для {SYMBOL}...")
    leverage_result = position.set_leverage(http_session, SYMBOL, LEVERAGE)
    if not leverage_result.get("ok"):
        if leverage_result.get("error_type") == "leverage_too_high":
            max_lev = leverage_result.get("max_leverage")
            notification_text = (
                f"❌ Позиция не открыта: ограничение плеча\n\n"
                f"📊 Символ: {SYMBOL}\n"
                f"🎯 Запрошено: {LEVERAGE}x\n"
                f"📉 Максимум по инструменту: {max_lev}x\n"
                f"ℹ️ По правилам проекта снижение плеча отключено"
            )
            send_notification_task.delay(notification_text)
        logger.error(f"❌ Не удалось установить кредитное плечо {LEVERAGE}x. Остановка алгоритма.")
        return
    if leverage_result.get("was_capped"):
        logger.warning(
            "⚠️ Для %s запрошено плечо %sx, но биржа разрешает максимум %sx. Применено %sx",
            SYMBOL,
            LEVERAGE,
            leverage_result.get("max_leverage"),
            leverage_result.get("applied_buy"),
        )
    logger.info(f"✅ Кредитное плечо {LEVERAGE}x установлено")

    force_one_way = os.getenv("FORCE_LINEAR_ONE_WAY", "true").strip().lower() in ("true", "1", "yes")
    if force_one_way:
        position.try_switch_linear_one_way(http_session, SYMBOL)

    # ============================================
    # ШАГ 2.1: ПРОВЕРКА НАЛИЧИЯ ОТКРЫТОЙ ПОЗИЦИИ И СОЗДАНИЕ ОБЪЕКТА ТРЕЙЛИНГ СТОПА
    # ============================================
    logger.info(f"🔍 Проверяю наличие открытой позиции по символу {SYMBOL}...")
    if position.if_position_open(http_session, SYMBOL):
        logger.warning(f"⚠️ По символу {SYMBOL} уже есть открытая позиция!")
        logger.warning(f"🛑 Алгоритм не будет запущен - дубликат отфильтрован")
        
        # Отправка уведомления подписчикам
        notification_text = (
            f"⚠️ Дубликат отфильтрован\n\n"
            f"📊 Символ: {SYMBOL}\n"
            f"ℹ️ По этой монете уже ведется торговля"
        )
        send_notification_task.delay(notification_text)
        logger.info(f"✅ Уведомление отправлено подписчикам о фильтрации дубликата")
        return
    
    logger.info(f"✅ Открытых позиций по {SYMBOL} не найдено, продолжаю запуск алгоритма")

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
    logger.info(
        f"🧮 Рассчитываю количество монет для суммы {USDT_AMOUNT} (* 10) USDT..."
    )
    qty = calculator.calculate_qty(SYMBOL, ALGORITHMS_SUM_FOR_TRADES, http_session)
    logger.info(f"✅ Рассчитанное количество: {qty} {SYMBOL}")
    
    # ============================================
    # ШАГ 5.1: ОТКРЫТИЕ ПОЗИЦИИ
    # ============================================
    logger.info(f"📝 Открываю {POSITION_SIDE} позицию на {qty} {SYMBOL}...")
    leg_idx = _hedge_leg_position_idx(POSITION_SIDE)
    order_result = orders.place_order(SYMBOL, qty, POSITION_SIDE, "Market", http_session)
    if order_result and order_result.get("retCode") == 0:
        ACTIVE_POSITION_IDX = None
    else:
        logger.warning(
            "Повтор входа Market с positionIdx=%s (hedge / несовпадение режима позиции)",
            leg_idx,
        )
        order_result = orders.place_order(
            SYMBOL, qty, POSITION_SIDE, "Market", http_session, position_idx=leg_idx
        )
        if order_result and order_result.get("retCode") == 0:
            ACTIVE_POSITION_IDX = leg_idx
        else:
            ACTIVE_POSITION_IDX = None

    if order_result and order_result.get('retCode') == 0:
        logger.info(f"✅ Позиция успешно открыта!")
        logger.info(f"   ID ордера: {order_result.get('result', {}).get('orderId', 'N/A')}")

        # ------------------------------------------
        # Отправка уведомления подписчикам
        # ------------------------------------------
        notification_text = (
        f"🚀 Алгоритм запущен!\n\n"
        f"📊 Символ: {SYMBOL}\n"
        f"💰 Сумма: {USDT_AMOUNT} USDT\n"
        f"📈 Сторона: {POSITION_SIDE}\n"
        )
        send_notification_task.delay(notification_text)
        logger.info(f"✅ Уведомление отправлено подписчикам")

        trailing_stop = TrailingStop(
            symbol=SYMBOL,
            session=http_session,
            trigger_percentage=TRIGGER_TS_PERCENTAGE,
            position_side=POSITION_SIDE,
            offset_percentage=0.1,
            position_idx=ACTIVE_POSITION_IDX,
        )
        logger.info(
            "📊 Трейлинг стоп создан (шаг: %s%%, positionIdx=%s)",
            TRIGGER_TS_PERCENTAGE,
            ACTIVE_POSITION_IDX,
        )
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
        rows = position_data["result"]["list"]
        position_info = None
        for row in rows:
            sz = float(row.get("size", 0) or 0)
            if sz <= 0:
                continue
            if ACTIVE_POSITION_IDX is not None:
                if int(row.get("positionIdx", 0) or 0) == int(ACTIVE_POSITION_IDX):
                    position_info = row
                    break
            else:
                position_info = row
                break
        if position_info is None and rows:
            position_info = rows[0]
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
        orders.set_stop_loss(SYMBOL, stop_loss_price, http_session, position_idx=ACTIVE_POSITION_IDX)
        logger.info(f"✅ Стоп-лосс успешно установлен")
    except Exception as e:
        logger.error(f"❌ Ошибка установки стоп-лосса: {e}")
        return

    logger.info(f"📝 Устанавливаю {COUNT_LIMIT_ORDERS} лимитных ордеров на {SYMBOL}...")
    place_n_limit_order = orders.place_n_limit_order(
        SYMBOL,
        ALGORITHMS_SUM_FOR_TRADES,
        POSITION_SIDE,
        entry_price,
        http_session,
        COUNT_LIMIT_ORDERS,
        LIMIT_PERCENTAGE,
        position_idx=ACTIVE_POSITION_IDX,
    )

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

    monitoring_active = True
    exit_reason = "мониторинг остановлен"
    try:
        price_stream.run_forever()
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки (Ctrl+C)")
        exit_reason = "прервано (Ctrl+C)"
    except Exception as e:
        logger.error(f"❌ Ошибка в WebSocket: {e}")
        exit_reason = f"ошибка WebSocket: {e}"
    finally:
        if monitoring_active and not completion_notified and SYMBOL:
            pnl_sign = "+" if pnl_usdt >= 0 else ""
            ep = entry_price if entry_price is not None else 0.0
            summary = (
                f"🏁 Short BU TS limit завершён\n\n"
                f"📊 Символ: {SYMBOL}\n"
                f"📌 Причина: {exit_reason}\n"
                f"💰 Цена входа: {ep:.8g}\n"
                f"💵 PnL: {pnl_sign}{pnl_usdt:.2f} USDT\n"
                f"📊 Изменение от входа: {price_change_percent:.2f}%"
            )
            try:
                send_notification_task.delay(summary)
                logger.info("Уведомление подписчикам: завершение сессии (без дубля с закрытием позиции)")
            except Exception as notify_err:
                logger.error("Не удалось отправить финальное уведомление: %s", notify_err)
        if should_stop:
            logger.info("🛑 Алгоритм остановлен по флагу should_stop")
        logger.info("✅ Функция start_trading завершена")
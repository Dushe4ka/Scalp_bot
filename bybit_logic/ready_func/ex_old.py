"""
Стратегия шорт-позиций с усреднением для работы через Celery
Адаптированная версия для приема сигналов через вебхуки
"""
from pybit.unified_trading import WebSocket, HTTP
import asyncio
from typing import Optional
from config import API_KEY, API_SECRET, DEMO_API_KEY, DEMO_API_SECRET, TELEGRAM_BOT_TOKEN
from database.subscribers import get_subscribers as get_cached_subscribers

get_all_subscribed_users = get_cached_subscribers
from utils.send_tg_message import (
    notify_position_opened,
    notify_averaging_order_placed,
    notify_averaging_executed,
    notify_take_profit_reached,
    notify_breakeven_moved,
    notify_position_closed,
    notify_stop_loss_triggered,
    notify_strategy_error
)
from bybit.stop_all_orders import stop_trading_by_symbol
from logger_config import setup_logger

logger = setup_logger(__name__)

# Настройки по умолчанию для стратегии
DEFAULT_USDT_AMOUNT = 100
DEFAULT_AVERAGING_PERCENT = 10.0
DEFAULT_INITIAL_TP_PERCENT = 3.0
DEFAULT_BREAKEVEN_STEP = 2.0
DEFAULT_STOP_LOSS_PERCENT = 15.0


class ShortAveragingStrategyCelery:
    """Стратегия шорт-позиций с усреднением для работы через Celery - БЫСТРАЯ ВЕРСИЯ"""
    
    def __init__(
        self,
        symbol: str,
        usdt_amount: float = DEFAULT_USDT_AMOUNT,
        averaging_percent: float = DEFAULT_AVERAGING_PERCENT,
        initial_tp_percent: float = DEFAULT_INITIAL_TP_PERCENT,
        breakeven_step: float = DEFAULT_BREAKEVEN_STEP,
        stop_loss_percent: float = DEFAULT_STOP_LOSS_PERCENT,
        use_demo: bool = True
    ):
        """
        Инициализация стратегии
        
        Args:
            symbol: Торговая пара (например, "BTCUSDT")
            usdt_amount: Сумма в USDT для открытия позиции
            averaging_percent: Процент для усреднения (по умолчанию 10%)
            initial_tp_percent: Начальный тейк-профит (по умолчанию 3%)
            breakeven_step: Шаг перемещения безубытка (по умолчанию 2%)
            stop_loss_percent: Стоп-лосс после усреднения (по умолчанию 15%)
            use_demo: Использовать демо-счет
        """
        self.symbol = symbol.upper()
        self.usdt_amount = usdt_amount
        self.averaging_percent = averaging_percent
        self.initial_tp_percent = initial_tp_percent
        self.breakeven_step = breakeven_step
        self.stop_loss_percent = stop_loss_percent
        self.use_demo = use_demo
        
        # Инициализация сессии
        # Выбираем ключи в зависимости от режима
        api_key = DEMO_API_KEY if use_demo else API_KEY
        api_secret = DEMO_API_SECRET if use_demo else API_SECRET
        
        self.session = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=api_secret,
            demo=use_demo
        )
        
        # Получаем информацию о символе
        self.qty_precision = None
        self.min_qty = None
        self.max_qty = None
        self._load_symbol_info()
        
        # Состояние позиции
        self.position_qty = 0
        self.entry_price = None  # Изначальная цена входа
        self.initial_entry_price = None  # Сохраняем изначальную цену для расчетов
        self.averaged_price = None  # Средняя цена входа (получаем из API)
        self.is_averaged = False
        self.averaging_order_id = None
        
        # Состояние тейк-профита и безубытка
        self.tp_price = None
        self.fake_tp_price = None  # ✨ НОВОЕ: 2% фиктивный TP после усреднения
        self.breakeven_price = None
        self.best_profit_percent = 0
        
        # Флаги состояния
        self.position_opened = False
        self.stop_loss_price = None
        self.stop_loss_order_id = None  # ID стоп-лосс ордера
        self.breakeven_order_id = None  # ID безубыток ордера
        
        # Счетчик попыток открытия
        self.open_attempts = 0
        self.max_open_attempts = 5
        self.failed_to_open = False
        self.last_error = None
        
        # WebSocket для мониторинга цены
        self.ws = None
        self.should_stop = False
        
        # Счетчик для периодического вывода статуса
        self.message_counter = 0
        self.status_interval = 10
        
        # ✨ НОВОЕ: Один event loop для всех операций
        self.loop = None
        
        # ✨ НОВОЕ: Отслеживание пиковой прибыли (важно!)
        self.peak_profit_percent = 0.0
        
        # ✨ НОВОЕ: Редкие проверки (ТОЛЬКО для некритичных операций)
        self.last_position_check = 0
        self.position_check_interval = 5.0  # Проверяем существование позиции раз в 5 секунд
        self.last_averaging_check = 0
        self.averaging_check_interval = 0.1  # Проверяем усреднение раз в 0.1 сек
        
        # ✨ НОВОЕ: Уменьшаем частоту логирования
        self.log_counter = 0
        self.log_interval = 10  # Логируем каждый 10-й тик
        
        # ✨ НОВОЕ: Счетчик обработанных тиков для статистики
        self.ticks_processed = 0
        self.start_time = None
        
        # ✨ НОВОЕ: Флаг для отслеживания фиктивного TP
        self.fake_tp_reached = False
        
        logger.info(f"[{self.symbol}] Стратегия инициализирована в БЫСТРОМ режиме")

    def _ensure_event_loop(self):
        """Создает event loop если его нет"""
        if not self.loop:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    async def safe_send_notification(self, notification_func, *args, **kwargs):
        """Безопасная отправка уведомления с использованием кэшированных подписчиков"""
        try:
            # ✨ ИСПРАВЛЕНИЕ: Используем кэшированных подписчиков вместо асинхронной БД
            # Получаем подписчиков из кэша (синхронно, не зависит от event loop)
            chat_ids = get_cached_subscribers()
            
            if not chat_ids:
                logger.warning(f"[{self.symbol}] Нет подписчиков для отправки уведомления")
                return
            
            logger.debug(f"[{self.symbol}] Отправляем уведомление {len(chat_ids)} подписчикам")
            
            # ✨ ИСПРАВЛЕНИЕ: Проверяем и создаем event loop если нужно
            try:
                loop = asyncio.get_running_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
            except RuntimeError:
                # Если нет активного loop или он закрыт, создаем новый
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Правильно формируем аргументы: chat_ids, bot_token, остальные аргументы
            if args and len(args) > 0:
                # Первый аргумент должен быть bot_token, добавляем chat_ids в начало
                new_args = (chat_ids, args[0]) + args[1:]
                await notification_func(*new_args, **kwargs)
            else:
                # Если нет аргументов, добавляем chat_ids и bot_token
                await notification_func(chat_ids, TELEGRAM_BOT_TOKEN, **kwargs)
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка отправки уведомления: {e}")
            # Fallback: пытаемся отправить через синхронную функцию
            try:
                self._send_notification_fallback(notification_func, *args, **kwargs)
            except Exception as fallback_error:
                logger.error(f"[{self.symbol}] Fallback отправка также не удалась: {fallback_error}")
    
    def _send_notification_fallback(self, notification_func, *args, **kwargs):
        """Fallback метод для отправки уведомлений через отдельный поток"""
        import threading
        import asyncio
        
        def run_in_thread():
            try:
                # Создаем новый event loop в отдельном потоке
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Получаем подписчиков синхронно
                chat_ids = get_cached_subscribers()
                if not chat_ids:
                    return
                
                # Правильно формируем аргументы: chat_ids, bot_token, остальные аргументы
                if args and len(args) > 0:
                    # Первый аргумент должен быть bot_token, добавляем chat_ids в начало
                    new_args = (chat_ids, args[0]) + args[1:]
                    loop.run_until_complete(notification_func(*new_args, **kwargs))
                else:
                    # Если нет аргументов, добавляем chat_ids и bot_token
                    loop.run_until_complete(notification_func(chat_ids, TELEGRAM_BOT_TOKEN, **kwargs))
                    
            except Exception as e:
                logger.error(f"[{self.symbol}] Ошибка в fallback потоке: {e}")
            finally:
                try:
                    loop.close()
                except:
                    pass
        
        # Запускаем в отдельном потоке с timeout
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join(timeout=10)  # Ждем максимум 10 секунд

    def _load_symbol_info(self):
        """Загружает информацию о символе и правилах торговли"""
        try:
            response = self.session.get_instruments_info(
                category="linear",
                symbol=self.symbol
            )
            
            if response.get('retCode') == 0:
                instruments = response.get('result', {}).get('list', [])
                if len(instruments) > 0:
                    instrument = instruments[0]
                    lot_size_filter = instrument.get('lotSizeFilter', {})
                    
                    qty_step = float(lot_size_filter.get('qtyStep', '0.01'))
                    self.min_qty = float(lot_size_filter.get('minOrderQty', '0.01'))
                    self.max_qty = float(lot_size_filter.get('maxOrderQty', '1000000'))
                    
                    self.qty_precision = len(str(qty_step).rstrip('0').split('.')[-1])
                    
                    logger.info(f"\n📊 Информация о символе {self.symbol}:")
                    logger.info(f"   Шаг qty: {qty_step}")
                    logger.info(f"   Точность: {self.qty_precision} знаков")
                    logger.info(f"   Мин. qty: {self.min_qty}")
                    logger.info(f"   Макс. qty: {self.max_qty}")
                else:
                    logger.warning(f"[{self.symbol}] Символ не найден, используем значения по умолчанию")
                    self.qty_precision = 3
                    self.min_qty = 0.001
                    self.max_qty = 1000000
            else:
                logger.warning(
                    f"[{self.symbol}] Ошибка получения информации: {response.get('retMsg')}"
                )
                self.qty_precision = 3
                self.min_qty = 0.001
                self.max_qty = 1000000
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Исключение при загрузке информации: {e}")
            self.qty_precision = 3
            self.min_qty = 0.001
            self.max_qty = 1000000

    def calculate_qty(self, price: float) -> float:
        """Рассчитывает количество актива для покупки на заданную сумму USDT"""
        qty = self.usdt_amount / price
        
        if self.qty_precision is not None:
            qty = round(qty, self.qty_precision)
        else:
            qty = round(qty, 3)
        
        if self.min_qty and qty < self.min_qty:
            logger.warning(
                f"[{self.symbol}] Qty {qty} < min {self.min_qty}, используем минимальное"
            )
            qty = self.min_qty
        
        if self.max_qty and qty > self.max_qty:
            logger.warning(
                f"[{self.symbol}] Qty {qty} > max {self.max_qty}, используем максимальное"
            )
            qty = self.max_qty
        
        return qty

    def check_position_exists(self) -> bool:
        """Проверяет существование открытой позиции на бирже"""
        try:
            response = self.session.get_positions(
                category="linear",
                symbol=self.symbol
            )
            
            if response.get('retCode') == 0:
                positions = response.get('result', {}).get('list', [])
                for pos in positions:
                    size = float(pos.get('size', 0))
                    if size > 0:
                        return True
            return False
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка проверки позиции: {e}")
            return False

    def check_open_orders_exist(self) -> bool:
        """Проверяет существование открытых ордеров на бирже"""
        try:
            response = self.session.get_open_orders(
                category="linear",
                symbol=self.symbol
            )
            
            if response.get('retCode') == 0:
                orders = response.get('result', {}).get('list', [])
                if len(orders) > 0:
                    logger.info(f"[{self.symbol}] Найдено {len(orders)} открытых ордеров")
                    return True
            return False
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка проверки ордеров: {e}")
            return False

    def check_active_trading(self) -> bool:
        """Проверяет наличие активной торговли (позиций или ордеров)"""
        has_position = self.check_position_exists()
        has_orders = self.check_open_orders_exist()
        
        if has_position:
            logger.warning(f"[{self.symbol}] ⚠️ Обнаружена открытая позиция! Торговля уже активна.")
            return True
            
        if has_orders:
            logger.warning(f"[{self.symbol}] ⚠️ Обнаружены открытые ордера! Торговля уже активна.")
            return True
            
        return False

    def get_position_avg_price(self) -> Optional[float]:
        """Получает среднюю цену входа позиции из API"""
        try:
            response = self.session.get_positions(
                category="linear",
                symbol=self.symbol
            )
            
            if response.get('retCode') == 0:
                positions = response.get('result', {}).get('list', [])
                for pos in positions:
                    size = float(pos.get('size', 0))
                    if size > 0:
                        avg_price = float(pos.get('avgPrice', 0))
                        if avg_price > 0:
                            logger.info(f"[{self.symbol}] Средняя цена входа из API: {avg_price:.8g}")
                            return avg_price
            return None
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка получения средней цены: {e}")
            return None

    async def open_short_position(self, current_price: float) -> bool:
        """Открывает шорт-позицию с повторными попытками"""
        if self.open_attempts >= self.max_open_attempts:
            if not self.failed_to_open:
                self.failed_to_open = True
                error_msg = (
                    f"Превышено максимальное количество попыток открытия позиции: "
                    f"{self.max_open_attempts}. Последняя ошибка: {self.last_error}"
                )
                logger.error(f"[{self.symbol}] {error_msg}")
                
                # Уведомляем об ошибке
                await self.safe_send_notification(
                    notify_strategy_error,
                    TELEGRAM_BOT_TOKEN, self.symbol, 
                    error_msg, "SHORT_AVERAGING"
                )
            return False
        
        try:
            self.open_attempts += 1
            qty = self.calculate_qty(current_price)
            
            logger.info(f"🚀 Попытка #{self.open_attempts}/{self.max_open_attempts} - Открываем ШОРТ позицию...")
            logger.info(f"💰 Сумма: {self.usdt_amount} USDT")
            logger.info(f"📊 Цена: {current_price:.8g}")
            logger.info(f"📈 Количество: {qty} (точность: {self.qty_precision} знаков)")
            
            # Открываем шорт-позицию
            order = self.session.place_order(
                category="linear",
                symbol=self.symbol,
                side="Sell",
                orderType="Market",
                qty=qty,
            )
            
            if order.get('retCode') == 0:
                self.entry_price = current_price
                self.initial_entry_price = current_price  # Сохраняем изначальную цену
                self.position_qty = qty
                self.position_opened = True
                
                # Рассчитываем цену тейк-профита (для шорта это НИЖЕ)
                self.tp_price = self.entry_price * (1 - self.initial_tp_percent / 100)
                
                logger.info("✅ ШОРТ позиция открыта!")
                logger.info(f"💵 Цена входа: {self.entry_price:.8g}")
                logger.info(f"🎯 Тейк-профит: {self.tp_price:.8g} (-{self.initial_tp_percent}%)")
                
                # Отправляем уведомление об открытии позиции
                await self.safe_send_notification(
                    notify_position_opened,
                    TELEGRAM_BOT_TOKEN, self.symbol,
                    self.entry_price, self.position_qty, self.usdt_amount,
                    self.tp_price, self.initial_tp_percent, "SHORT"
                )
                
                # Выставляем лимитный ордер на усреднение
                await self.place_averaging_order()
                
                return True
            else:
                error_msg = order.get('retMsg', 'Неизвестная ошибка')
                self.last_error = error_msg
                logger.error(
                    f"[{self.symbol}] Ошибка открытия позиции "
                    f"(попытка {self.open_attempts}/{self.max_open_attempts}): {error_msg}"
                )
                return False
                
        except Exception as e:
            self.last_error = str(e)
            logger.error(
                f"[{self.symbol}] Исключение при открытии позиции "
                f"(попытка {self.open_attempts}/{self.max_open_attempts}): {e}"
            )
            return False

    async def place_averaging_order(self) -> bool:
        """Выставляет лимитный ордер на усреднение +10% от цены входа"""
        try:
            # ✨ ИСПРАВЛЕНИЕ: Усреднение +10% от цены входа (для шорта это ВЫШЕ)
            averaging_price = self.entry_price * (1 + self.averaging_percent / 100)
            qty = self.calculate_qty(averaging_price)  # Сумма в USDT по новой цене
            
            logger.info("📝 Выставляем лимитный ордер на усреднение...")
            logger.info(f"💰 Цена усреднения: {averaging_price:.8g} (+{self.averaging_percent}% от входа)")
            logger.info(f"📈 Количество: {qty} (сумма: {self.usdt_amount} USDT)")
            logger.info(f"📊 Округлено до {self.qty_precision} знаков")
            
            order = self.session.place_order(
                category="linear",
                symbol=self.symbol,
                side="Sell",
                orderType="Limit",
                qty=qty,
                price=averaging_price,
            )
            
            if order.get('retCode') == 0:
                self.averaging_order_id = order.get('result', {}).get('orderId')
                logger.info(f"✅ Лимитный ордер выставлен! ID: {self.averaging_order_id}")
                
                # Отправляем уведомление
                await self.safe_send_notification(
                    notify_averaging_order_placed,
                    TELEGRAM_BOT_TOKEN, self.symbol,
                    averaging_price, self.averaging_percent, qty
                )
                
                return True
            else:
                logger.error(
                    f"[{self.symbol}] Ошибка выставления ордера: "
                    f"{order.get('retMsg', 'Неизвестная ошибка')}"
                )
                return False
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Исключение при выставлении ордера: {e}")
            return False

    def check_averaging_by_position_size(self) -> bool:
        """Альтернативная проверка усреднения через изменение размера позиции"""
        try:
            response = self.session.get_positions(category="linear", symbol=self.symbol)
            if response.get('retCode') == 0:
                positions = response.get('result', {}).get('list', [])
                for pos in positions:
                    size = float(pos.get('size', 0))
                    if size > 0:
                        # Если размер позиции увеличился, значит усреднение сработало
                        if size > self.position_qty:
                            logger.info(f"[{self.symbol}] ✅ Размер позиции увеличился: {self.position_qty} -> {size}")
                            return True
            return False
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка проверки размера позиции: {e}")
            return False

    def check_averaging_order_filled(self) -> bool:
        """Проверяет, был ли исполнен ордер на усреднение"""
        try:
            if not self.averaging_order_id:
                logger.debug(f"[{self.symbol}] Нет ID ордера на усреднение")
                return False
            
            logger.debug(f"[{self.symbol}] Проверяем ордер {self.averaging_order_id}")
            
            # 1. Проверяем открытые ордера
            response = self.session.get_open_orders(
                category="linear",
                symbol=self.symbol,
                orderId=self.averaging_order_id
            )
            
            if response.get('retCode') == 0:
                orders = response.get('result', {}).get('list', [])
                logger.debug(f"[{self.symbol}] Открытые ордера: {len(orders)}")
                
                if len(orders) == 0:
                    # Ордера нет в открытых - проверяем историю
                    logger.debug(f"[{self.symbol}] Ордер не в открытых, проверяем историю...")
                    
                    history = self.session.get_order_history(
                        category="linear",
                        symbol=self.symbol,
                        orderId=self.averaging_order_id
                    )
                    
                    if history.get('retCode') == 0:
                        orders_hist = history.get('result', {}).get('list', [])
                        logger.debug(f"[{self.symbol}] История ордеров: {len(orders_hist)}")
                        
                        if len(orders_hist) > 0:
                            order = orders_hist[0]
                            order_id = order.get('orderId')
                            order_status = order.get('orderStatus')
                            order_side = order.get('side')
                            
                            logger.debug(f"[{self.symbol}] Ордер: ID={order_id}, Status={order_status}, Side={order_side}")
                            
                            # Проверяем, что это именно наш ордер И он исполнен
                            if (order_id == self.averaging_order_id and 
                                order_status == 'Filled' and
                                order_side == 'Sell'):  # Для шорта это Sell
                                logger.info(f"[{self.symbol}] ✅ Ордер на усреднение исполнен!")
                                return True
                            else:
                                logger.debug(f"[{self.symbol}] Ордер не исполнен: {order_status}")
                    else:
                        logger.debug(f"[{self.symbol}] Ошибка получения истории: {history.get('retMsg')}")
                else:
                    logger.debug(f"[{self.symbol}] Ордер еще в открытых")
            else:
                logger.debug(f"[{self.symbol}] Ошибка получения открытых ордеров: {response.get('retMsg')}")
            
            return False
            
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка проверки ордера: {e}")
            return False

    async def place_stop_loss_order(self) -> bool:
        """Выставляет стоп-лосс ордер в Bybit"""
        try:
            logger.info(f"[{self.symbol}] 🛡️ Выставляем стоп-лосс ордер...")
            logger.info(f"[{self.symbol}] 💰 Цена стоп-лосса: {self.stop_loss_price:.6f} (+{self.stop_loss_percent}%)")
            logger.info(f"[{self.symbol}] 📈 Количество: {self.position_qty}")
            
            # Выставляем стоп-лосс ордер (для шорта это Buy Stop)
            order = self.session.place_order(
                category="linear",
                symbol=self.symbol,
                side="Buy",  # Для шорта стоп-лосс это Buy
                orderType="Stop",  # ✨ ИСПРАВЛЕНИЕ: Stop вместо StopMarket
                qty=self.position_qty,
                stopPrice=self.stop_loss_price,
                triggerBy="LastPrice"  # Срабатывает по последней цене
            )
            
            if order.get('retCode') == 0:
                self.stop_loss_order_id = order.get('result', {}).get('orderId')
                logger.info(f"[{self.symbol}] ✅ Стоп-лосс ордер выставлен! ID: {self.stop_loss_order_id}")
                return True
            else:
                error_msg = order.get('retMsg', 'Неизвестная ошибка')
                logger.error(f"[{self.symbol}] ❌ Ошибка выставления стоп-лосса: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Исключение при выставлении стоп-лосса: {e}")
            return False

    async def place_breakeven_order(self, current_price: float, profit_percent: float) -> bool:
        """Выставляет безубыток ордер в Bybit"""
        try:
            # Отменяем предыдущий безубыток ордер
            if self.breakeven_order_id:
                await self.cancel_breakeven_order()
            
            # ✨ ИСПРАВЛЕНИЕ: НЕ отменяем стоп-лосс - позволяем множественные стоп-ордера
            # Стоп-лосс защищает от больших убытков, безубыток защищает прибыль
            
            logger.info(f"[{self.symbol}] 🔒 Выставляем безубыток на {profit_percent:.1f}%...")
            logger.info(f"[{self.symbol}] 💰 Цена безубытка: {current_price:.6f}")
            logger.info(f"[{self.symbol}] 📈 Количество: {self.position_qty}")
            
            # ✨ НОВОЕ: Показываем статус множественных стоп-ордеров
            if self.stop_loss_order_id:
                logger.info(f"[{self.symbol}] 🛡️ Стоп-лосс активен: {self.stop_loss_price:.6f} (ID: {self.stop_loss_order_id})")
            else:
                logger.info(f"[{self.symbol}] ⚠️ Стоп-лосс не установлен")
            
            # Выставляем Buy Stop ордер для закрытия шорта
            order = self.session.place_order(
                category="linear",
                symbol=self.symbol,
                side="Buy",  # Покупка для закрытия шорта
                orderType="Stop",  # ✨ ИСПРАВЛЕНИЕ: Stop вместо StopMarket
                qty=self.position_qty,
                stopPrice=current_price,
                triggerBy="LastPrice"
            )
            
            if order.get('retCode') == 0:
                self.breakeven_order_id = order.get('result', {}).get('orderId')
                self.breakeven_price = current_price
                logger.info(f"[{self.symbol}] ✅ Безубыток ордер выставлен! ID: {self.breakeven_order_id}")
                return True
            else:
                error_msg = order.get('retMsg', 'Неизвестная ошибка')
                logger.error(f"[{self.symbol}] ❌ Ошибка выставления безубытка: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Исключение при выставлении безубытка: {e}")
            return False

    async def cancel_breakeven_order(self) -> bool:
        """Отменяет безубыток ордер"""
        try:
            if not self.breakeven_order_id:
                return True
            
            logger.info(f"[{self.symbol}] 🔄 Отменяем безубыток ордер {self.breakeven_order_id}")
            
            response = self.session.cancel_order(
                category="linear",
                symbol=self.symbol,
                orderId=self.breakeven_order_id
            )
            
            if response.get('retCode') == 0:
                logger.info(f"[{self.symbol}] ✅ Безубыток ордер отменен")
                self.breakeven_order_id = None
                return True
            else:
                error_msg = response.get('retMsg', 'Неизвестная ошибка')
                if 'not exists' in error_msg.lower() or 'not found' in error_msg.lower():
                    logger.info(f"[{self.symbol}] Безубыток ордер уже не существует")
                    self.breakeven_order_id = None
                    return True
                logger.warning(f"[{self.symbol}] Ошибка отмены безубытка: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Исключение при отмене безубытка: {e}")
            return False

    async def apply_averaging(self, current_price: float) -> bool:
        """Применяет логику после усреднения"""
        try:
            logger.info(f"[{self.symbol}] Усреднение сработало!")
            
            # ✨ ИСПРАВЛЕНИЕ: Получаем среднюю цену входа из API
            api_avg_price = self.get_position_avg_price()
            if api_avg_price:
                self.averaged_price = api_avg_price
                logger.info(f"[{self.symbol}] Средняя цена входа из API: {self.averaged_price:.8g}")
            else:
                # Fallback: рассчитываем вручную (если API не работает)
                averaging_price = self.entry_price * (1 + self.averaging_percent / 100)  # +10% от входа
                new_qty = self.calculate_qty(averaging_price)
                total_qty = self.position_qty + new_qty
                self.averaged_price = (
                    self.entry_price * self.position_qty + averaging_price * new_qty
                ) / total_qty
                logger.warning(f"[{self.symbol}] Используем расчетную среднюю цену: {self.averaged_price:.8g}")
            
            # Получаем обновленное количество из API
            try:
                response = self.session.get_positions(category="linear", symbol=self.symbol)
                if response.get('retCode') == 0:
                    positions = response.get('result', {}).get('list', [])
                    for pos in positions:
                        size = float(pos.get('size', 0))
                        if size > 0:
                            self.position_qty = size
                            break
            except Exception as e:
                logger.warning(f"[{self.symbol}] Не удалось получить обновленное количество: {e}")
            
            self.is_averaged = True
            
            # ✨ ИСПРАВЛЕНИЕ: Устанавливаем стоп-лосс относительно новой средней цены
            self.stop_loss_price = self.averaged_price * (1 + self.stop_loss_percent / 100)
            
            # ✨ НОВОЕ: Выставляем стоп-лосс ордер в Bybit
            await self.place_stop_loss_order()
            
            # ✨ ИСПРАВЛЕНИЕ: Новый тейк-профит от усредненной цены
            self.tp_price = self.averaged_price * (1 - self.initial_tp_percent / 100)
            # ✨ НОВОЕ: 2% фиктивный TP от усредненной цены
            self.fake_tp_price = self.averaged_price * (1 - 0.02)  # 2% от усредненной цены
            self.best_profit_percent = 0
            # ✨ ВАЖНО: Сбрасываем безубыток, чтобы он пересчитался от усредненной цены
            self.breakeven_price = None
            
            logger.info(
                f"[{self.symbol}] Усредненная цена: {self.averaged_price:.6f}, "
                f"SL: {self.stop_loss_price:.6f}, TP: {self.tp_price:.6f}, "
                f"Fake TP: {self.fake_tp_price:.6f}, Qty: {self.position_qty}"
            )
            
            # Отправляем уведомление
            await self.safe_send_notification(
                notify_averaging_executed,
                TELEGRAM_BOT_TOKEN, self.symbol,
                self.averaged_price, self.position_qty,
                self.tp_price, self.initial_tp_percent,
                self.stop_loss_price, self.stop_loss_percent
            )
            
            return True
            
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка применения усреднения: {e}")
            return False

    async def update(self, current_price: float, current_time: float) -> Optional[str]:
        """Обновляет состояние стратегии - ПРОВЕРЯЕТ КАЖДЫЙ ТИК"""
        
        if not self.position_opened:
            return None
        
        # ✨ ПРИМЕЧАНИЕ: Проверка позиции теперь в handle_message для оптимизации
        
        # ✨ ИСПРАВЛЕНИЕ: Определяем базовую цену для расчетов
        # Если усреднение произошло, используем среднюю цену из API
        if self.is_averaged:
            # Периодически обновляем среднюю цену из API
            if current_time - self.last_position_check > self.position_check_interval:
                api_avg_price = self.get_position_avg_price()
                if api_avg_price:
                    self.averaged_price = api_avg_price
            base_price = self.averaged_price
        else:
            base_price = self.entry_price
        
        # ✨ НОВОЕ: Определяем цену для расчетов TP и БУ
        # ДО усреднения: от начальной цены входа
        # ПОСЛЕ усреднения: от усредненной цены
        tp_breakeven_base_price = self.averaged_price if self.is_averaged else self.entry_price
        
        # ✨ КРИТИЧНО: Рассчитываем прибыль на КАЖДОМ тике
        profit_percent = (base_price - current_price) / base_price * 100
        
        # ✨ НОВОЕ: Отслеживаем пиковую прибыль
        if profit_percent > self.peak_profit_percent:
            self.peak_profit_percent = profit_percent
        
        # ✅ КРИТИЧНО: Проверяем стоп-лосс НА КАЖДОМ ТИКЕ (без кэширования!)
        if self.is_averaged and self.stop_loss_price:
            if current_price >= self.stop_loss_price:
                logger.warning(
                    f"[{self.symbol}] 🚨 Стоп-лосс сработал! "
                    f"Цена: {current_price:.6f} >= {self.stop_loss_price:.6f}"
                )
                
                # Уведомление - НЕ блокируем, отправляем асинхронно
                await self.safe_send_notification(
                    notify_stop_loss_triggered,
                    TELEGRAM_BOT_TOKEN, self.symbol,
                    current_price, self.stop_loss_price
                )
                
                return "CLOSE"
        
        # ✨ ОПТИМИЗАЦИЯ: Проверяем усреднение чаще, но не на каждом тике
        if not self.is_averaged:
            # Проверяем по времени
            if current_time - self.last_averaging_check > self.averaging_check_interval:
                if self.check_averaging_order_filled():
                    await self.apply_averaging(current_price)
                self.last_averaging_check = current_time
            
            # ✨ НОВОЕ: Дополнительная проверка по цене - если цена достигла уровня усреднения
            averaging_price = self.entry_price * (1 + self.averaging_percent / 100)
            if current_price >= averaging_price:
                logger.info(f"[{self.symbol}] 🎯 Цена достигла уровня усреднения! {current_price:.6f} >= {averaging_price:.6f}")
                
                # Проверяем двумя способами
                order_filled = self.check_averaging_order_filled()
                position_increased = self.check_averaging_by_position_size()
                
                if order_filled or position_increased:
                    logger.info(f"[{self.symbol}] ✅ Усреднение подтверждено! Order: {order_filled}, Position: {position_increased}")
                    await self.apply_averaging(current_price)
                else:
                    logger.warning(f"[{self.symbol}] Цена достигла уровня усреднения, но усреднение не подтверждено!")
        
        # ✨ НОВОЕ: Проверяем 2% фиктивный TP после усреднения
        if self.is_averaged and self.fake_tp_price and current_price <= self.fake_tp_price:
            # Проверяем, что это первый раз когда достигаем фиктивный TP
            if not hasattr(self, 'fake_tp_reached') or not self.fake_tp_reached:
                self.fake_tp_reached = True
                logger.info(
                    f"[{self.symbol}] 🎯 Достигнут 2% фиктивный TP! "
                    f"Цена: {current_price:.6f} <= {self.fake_tp_price:.6f}"
                )
                # Фиктивный TP не закрывает позицию, только логируем
        
        # ✅ КРИТИЧНО: Логика тейк-профита с РЕАЛЬНЫМИ ОРДЕРАМИ
        if profit_percent >= self.initial_tp_percent:
            if not self.breakeven_price and not self.breakeven_order_id:
                # ✨ ИСПРАВЛЕНИЕ: Рассчитываем правильную цену безубытка для первого TP
                if self.is_averaged and self.averaged_price:
                    base_price = self.averaged_price
                else:
                    base_price = self.entry_price
                
                # Цена безубытка = базовая цена * (1 - profit_percent / 100)
                breakeven_price = base_price * (1 - profit_percent / 100)
                
                logger.info(
                    f"[{self.symbol}] 🎯 Достигнут TP {self.initial_tp_percent}%! "
                    f"Выставляем безубыток на: {breakeven_price:.6f} ({profit_percent:.1f}%)"
                )
                
                # Выставляем реальный безубыток ордер
                await self.place_breakeven_order(breakeven_price, profit_percent)
                self.best_profit_percent = profit_percent
                
                # Уведомление асинхронно
                await self.safe_send_notification(
                    notify_take_profit_reached,
                    TELEGRAM_BOT_TOKEN, self.symbol,
                    current_price, profit_percent, breakeven_price  # ✨ ИСПРАВЛЕНИЕ: используем правильную цену безубытка
                )
            else:
                # ✨ ИСПРАВЛЕНИЕ: Проверяем шаги безубытка - каждые 2% прибыли
                # При 3% прибыли: БУ = 3% (уже выставлен выше)
                # При 5% прибыли: БУ = 5% 
                # При 7% прибыли: БУ = 7%
                # При 9% прибыли: БУ = 9%
                # И так далее...
                breakeven_levels = [5.0, 7.0, 9.0, 11.0, 13.0, 15.0, 17.0, 19.0, 21.0, 23.0, 25.0]
                target_breakeven_percent = None
                
                for level in breakeven_levels:
                    if profit_percent >= level and self.best_profit_percent < level:
                        target_breakeven_percent = level
                        break
                
                # Если прибыль достигла нового уровня (5%, 7%, 9%, 11%, 13%, 15%, 17%, 19%, 21%, 23%, 25%)
                if target_breakeven_percent and self.breakeven_order_id:
                    old_breakeven = self.breakeven_price
                    
                    # ✨ ИСПРАВЛЕНИЕ: Рассчитываем правильную цену безубытка
                    if self.is_averaged and self.averaged_price:
                        base_price = self.averaged_price
                    else:
                        base_price = self.entry_price
                    
                    # Цена безубытка = базовая цена * (1 - target_breakeven_percent / 100)
                    breakeven_price = base_price * (1 - target_breakeven_percent / 100)
                    
                    logger.info(
                        f"[{self.symbol}] 🔒 Перемещаем безубыток: {old_breakeven:.6f} -> "
                        f"{breakeven_price:.6f} ({target_breakeven_percent:.1f}%)"
                    )
                    
                    # Выставляем новый безубыток ордер (старый отменится автоматически)
                    await self.place_breakeven_order(breakeven_price, target_breakeven_percent)
                    self.best_profit_percent = target_breakeven_percent
                    
                    # ✨ НОВОЕ: Показываем статус множественных стоп-ордеров после перемещения
                    if self.stop_loss_order_id:
                        logger.info(f"[{self.symbol}] 🛡️ Стоп-лосс остается активным: {self.stop_loss_price:.6f}")
                    else:
                        logger.warning(f"[{self.symbol}] ⚠️ Стоп-лосс не установлен после перемещения безубытка")
                    
                    await self.safe_send_notification(
                        notify_breakeven_moved,
                        TELEGRAM_BOT_TOKEN, self.symbol,
                        self.breakeven_price, target_breakeven_percent, profit_percent
                    )
        
        # ✅ КРИТИЧНО: Проверяем безубыток - теперь это делается через реальные ордера
        # Но оставляем fallback проверку на случай, если ордер не сработал
        if self.breakeven_price and current_price >= self.breakeven_price:
            logger.info(
                f"[{self.symbol}] 🏁 Безубыток сработал! "
                f"Цена: {current_price:.6f} >= {self.breakeven_price:.6f} "
                f"(Пик прибыли был: {self.peak_profit_percent:.2f}%)"
            )
            return "CLOSE"
        
        return None

    async def cancel_averaging_order(self) -> bool:
        """Отменяет лимитный ордер на усреднение с повторными попытками"""
        if not self.averaging_order_id:
            return True
        
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    f"[{self.symbol}] Попытка {attempt}/{max_attempts} отменить лимитный ордер"
                )
                response = self.session.cancel_order(
                    category="linear",
                    symbol=self.symbol,
                    orderId=self.averaging_order_id
                )
                
                if response.get('retCode') == 0:
                    logger.info(f"[{self.symbol}] Лимитный ордер успешно отменен")
                    return True
                else:
                    error_msg = response.get('retMsg', 'Неизвестная ошибка')
                    if 'not exists' in error_msg.lower() or 'not found' in error_msg.lower():
                        logger.info(f"[{self.symbol}] Лимитный ордер уже не существует")
                        return True
                    logger.warning(f"[{self.symbol}] Попытка {attempt}: {error_msg}")
                    
            except Exception as e:
                error_str = str(e)
                if 'not exists' in error_str.lower() or 'not found' in error_str.lower():
                    logger.info(f"[{self.symbol}] Лимитный ордер уже не существует")
                    return True
                logger.warning(f"[{self.symbol}] Исключение при попытке {attempt}: {e}")
            
            if attempt < max_attempts:
                await asyncio.sleep(0.5)
        
            return False

    async def stop_trading_for_symbol(self) -> bool:
        """Останавливает торговлю только для конкретной монеты"""
        try:
            logger.info(f"[{self.symbol}] 🛑 Останавливаем торговлю для {self.symbol}...")
            
            # ✨ ИСПРАВЛЕНИЕ: Используем функцию stop_trading_by_symbol 
            # которая отменяет ордера и закрывает позицию только для конкретной монеты
            stop_trading_by_symbol(self.symbol)
            
            # Очищаем локальные переменные
            self.breakeven_order_id = None
            self.stop_loss_order_id = None
            self.averaging_order_id = None
            
            logger.info(f"[{self.symbol}] ✅ Торговля для {self.symbol} остановлена")
            return True
            
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка остановки торговли: {e}")
            return False

    def stop_websocket(self):
        """Останавливает WebSocket соединение"""
        try:
            if self.ws:
                logger.info(f"[{self.symbol}] Закрываем WebSocket соединение...")
                self.ws.exit()
                self.ws = None
                logger.info(f"[{self.symbol}] WebSocket соединение закрыто")
        except Exception as e:
            logger.warning(f"[{self.symbol}] Ошибка при закрытии WebSocket: {e}")
    
    async def close_position(self) -> bool:
        """Закрывает позицию используя stop_trading_by_symbol"""
        try:
            logger.info(f"[{self.symbol}] Закрываем позицию...")
            
            # ✨ ИСПРАВЛЕНИЕ: Используем функцию остановки торговли только для конкретной монеты
            await self.stop_trading_for_symbol()
            
            # Получаем текущую цену для расчетов
            response = self.session.get_tickers(
                category="linear",
                symbol=self.symbol
            )
            current_price = None
            if response.get('retCode') == 0:
                tickers = response.get('result', {}).get('list', [])
                if len(tickers) > 0:
                    current_price = float(tickers[0].get('lastPrice', 0))
            
            logger.info(f"[{self.symbol}] Позиция успешно закрыта!")
            
            # ✨ ИСПРАВЛЕНИЕ: Рассчитываем прибыль/убыток относительно правильной базовой цены
            if self.is_averaged and self.averaged_price:
                base_price = self.averaged_price
            else:
                base_price = self.entry_price
            
            profit_percent = None
            profit_usdt = None
            
            if current_price and base_price:
                profit_percent = (base_price - current_price) / base_price * 100
                profit_usdt = (base_price - current_price) * self.position_qty
            
            # Определяем причину закрытия
            close_reason = "BREAKEVEN"
            if self.is_averaged and self.stop_loss_price and current_price:
                if current_price >= self.stop_loss_price:
                    close_reason = "STOP_LOSS"
            
            # Отправляем уведомление о закрытии
            await self.safe_send_notification(
                notify_position_closed,
                TELEGRAM_BOT_TOKEN, self.symbol,
                close_reason, base_price, current_price or 0,
                self.position_qty, profit_percent, profit_usdt,
                self.is_averaged
            )
            
            return True
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Исключение при закрытии позиции: {e}")
            return False

    def handle_message(self, message):
        """Обработчик сообщений из WebSocket - МАКСИМАЛЬНО БЫСТРЫЙ"""
        try:
            # Ранний выход при остановке
            if self.should_stop:
                return
            
            if 'data' not in message:
                return
            
            data = message['data']
            current_price = float(data.get('lastPrice', 0))
            
            if current_price <= 0:
                return
            
            # ✨ Импортируем time один раз в начале класса
            import time
            current_time = time.time()
            
            # Инициализация времени старта
            if self.start_time is None:
                self.start_time = current_time
            
            self.ticks_processed += 1
            
            # Автоматическое открытие позиции
            if not self.position_opened and not self.failed_to_open:
                self._ensure_event_loop()
                success = self.loop.run_until_complete(self.open_short_position(current_price))
                
                if success:
                    logger.info("✅ ШОРТ позиция успешно открыта!")
                
                if not success and self.failed_to_open:
                    self.should_stop = True
                    self.stop_websocket()
                return
            
            # ✨ КРИТИЧНО: Проверяем, что позиция еще открыта
            if self.position_opened:
                # Проверяем существование позиции периодически
                if current_time - self.last_position_check > self.position_check_interval:
                    if not self.check_position_exists():
                        logger.warning(f"[{self.symbol}] 🚨 Позиция закрыта вручную или не существует!")
                        self.should_stop = True
                        self.stop_websocket()
                        return
                    self.last_position_check = current_time
                # ✨ ИСПРАВЛЕНИЕ: Используем правильную базовую цену
                if self.is_averaged and self.averaged_price:
                    base_price = self.averaged_price
                else:
                    base_price = self.entry_price
                profit_percent = (base_price - current_price) / base_price * 100
                
                # ✨ КРИТИЧНО: Мгновенная проверка безубытка ПЕРЕД всем остальным!
                if self.breakeven_price and current_price >= self.breakeven_price:
                    logger.warning(f"🚨 МГНОВЕННОЕ срабатывание безубытка на {profit_percent:.2f}%!")
                    self._ensure_event_loop()
                    self.loop.run_until_complete(self.close_position())
                    self.should_stop = True
                    self.stop_websocket()
                    return
                
                # Логируем редко
                self.log_counter += 1
                if self.log_counter % self.log_interval == 0:
                    pnl_emoji = "📈" if profit_percent >= 0 else "📉"
                    pnl_sign = "+" if profit_percent >= 0 else ""
                    
                    # Статистика скорости обработки
                    elapsed = current_time - self.start_time
                    ticks_per_sec = self.ticks_processed / elapsed if elapsed > 0 else 0
                    
                    logger.info(
                        f"💰 Цена: {current_price:.8g} | {pnl_emoji} PnL: {pnl_sign}{profit_percent:.2f}% "
                        f"(Пик: {self.peak_profit_percent:.2f}%) | ⚡ {ticks_per_sec:.1f} тиков/сек"
                    )
                
                # Периодический статус
                self.message_counter += 1
                if self.message_counter % self.status_interval == 0:
                    averaged_status = "ДА" if self.is_averaged else "НЕТ"
                    logger.info(
                        f"🔧 Позиция ОТКРЫТА | Усреднение={averaged_status} | "
                        f"PnL={profit_percent:+.2f}% | Обработано {self.ticks_processed} тиков"
                    )
            
            # Создаем loop если нужно
            self._ensure_event_loop()
            
            # ✅ Основная логика update - проверяет ВСЕ на каждом тике
            action = self.loop.run_until_complete(self.update(current_price, current_time))
            
            if action == "CLOSE":
                logger.info(f"[{self.symbol}] Условие закрытия! Макс прибыль: {self.peak_profit_percent:.2f}%")
                self.loop.run_until_complete(self.close_position())
                self.should_stop = True
                self.stop_websocket()
                
            elif action == "STOP":
                logger.warning(f"⚠️ [{self.symbol}] Позиция закрыта вручную!")
                # Очищаем все ордера для этой монеты
                self.loop.run_until_complete(self.stop_trading_for_symbol())
                self.should_stop = True
                self.stop_websocket()
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка обработки: {e}", exc_info=True)

    async def run(self):
        """Запускает стратегию через WebSocket"""
        try:
            logger.info("\n" + "=" * 60)
            logger.info("🚀 СТРАТЕГИЯ ШОРТ С УСРЕДНЕНИЕМ (БЫСТРАЯ ВЕРСИЯ)")
            logger.info("=" * 60)
            logger.info(f"📊 Символ: {self.symbol}")
            logger.info(f"💰 Сумма: {self.usdt_amount} USDT")
            logger.info(f"📏 Точность: {self.qty_precision} знаков (мин: {self.min_qty})")
            logger.info(f"📈 Усреднение: +{self.averaging_percent}% от цены входа (сумма: {self.usdt_amount} USDT)")
            logger.info(f"🎯 Тейк-профит: {self.initial_tp_percent}%")
            logger.info(f"🔒 Безубыток шаг: {self.breakeven_step}%")
            logger.info(f"🛡️ Стоп-лосс: {self.stop_loss_percent}%")
            logger.info(f"⚡ Режим: ПРОВЕРКА КАЖДОГО ТИКА")
            logger.info("=" * 60)
            
            # ✨ КРИТИЧНО: Проверяем активную торговлю перед запуском
            logger.info(f"🔍 Проверяем активную торговлю для {self.symbol}...")
            if self.check_active_trading():
                logger.warning(f"🛑 Торговля для {self.symbol} уже активна! Игнорируем новый сигнал.")
                
                # Отправляем уведомление о том, что сигнал проигнорирован
                await self.safe_send_notification(
                    notify_strategy_error,
                    TELEGRAM_BOT_TOKEN, self.symbol,
                    f"Сигнал проигнорирован: торговля уже активна для {self.symbol}", 
                    "DUPLICATE_PREVENTION"
                )
                
                logger.info(f"✅ Сигнал для {self.symbol} успешно проигнорирован")
                return  # Выходим из стратегии
            
            logger.info(f"✅ Торговля для {self.symbol} не активна, начинаем стратегию")
            
            # ✨ Создаем ОДИН event loop для всей стратегии
            self._ensure_event_loop()
            
            # Инициализируем WebSocket
            self.ws = WebSocket(testnet=False, channel_type="linear")
            
            # Подписка на тикер
            self.ws.ticker_stream(self.symbol, self.handle_message)
            
            # Ждем остановки
            while not self.should_stop:
                await asyncio.sleep(0.1)  # Проверяем чаще для быстрой реакции
            
            logger.info("\n" + "=" * 60)
            logger.info(f"🏁 СТРАТЕГИЯ ЗАВЕРШЕНА | Обработано {self.ticks_processed} тиков")
            logger.info(f"📊 Максимальная прибыль: {self.peak_profit_percent:.2f}%")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"[{self.symbol}] Критическая ошибка: {e}", exc_info=True)
            
            await self.safe_send_notification(
                notify_strategy_error,
                TELEGRAM_BOT_TOKEN, self.symbol,
                str(e), "SHORT_AVERAGING"
            )
            
            raise
        
        finally:
            # Закрываем event loop
            if self.loop and not self.loop.is_closed():
                self.loop.close()
                self.loop = None
            
            # Закрываем WebSocket
            if self.ws:
                try:
                    self.ws.exit()
                except Exception as e:
                    logger.warning(f"Ошибка закрытия WS: {e}")
                finally:
                    self.ws = None


async def run_short_averaging_strategy(
    symbol: str,
    usdt_amount: float = DEFAULT_USDT_AMOUNT,
    averaging_percent: float = DEFAULT_AVERAGING_PERCENT,
    initial_tp_percent: float = DEFAULT_INITIAL_TP_PERCENT,
    breakeven_step: float = DEFAULT_BREAKEVEN_STEP,
    stop_loss_percent: float = DEFAULT_STOP_LOSS_PERCENT,
    use_demo: bool = True
):
    """
    Запускает стратегию шорт с усреднением
    
    Args:
        symbol: Торговый символ
        usdt_amount: Сумма в USDT
        averaging_percent: Процент усреднения
        initial_tp_percent: Начальный тейк-профит
        breakeven_step: Шаг безубытка
        stop_loss_percent: Стоп-лосс
        use_demo: Использовать демо-счет
    """
    strategy = ShortAveragingStrategyCelery(
        symbol=symbol,
        usdt_amount=usdt_amount,
        averaging_percent=averaging_percent,
        initial_tp_percent=initial_tp_percent,
        breakeven_step=breakeven_step,
        stop_loss_percent=stop_loss_percent,
        use_demo=use_demo
    )
    
    await strategy.run()


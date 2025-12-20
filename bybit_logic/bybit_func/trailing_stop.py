"""
Модуль для управления трейлинг стоп-лоссом

Простой и понятный класс для автоматического обновления стоп-лосса
при достижении определенного процента изменения цены

═══════════════════════════════════════════════════════════════════════════════
КАК ЭТО РАБОТАЕТ (простое объяснение):
═══════════════════════════════════════════════════════════════════════════════

Представьте, что вы купили монету за 100 USDT и установили трейлинг стоп с
шагом 1%. Вот как он работает:

1. АКТИВАЦИЯ (при достижении 2% прибыли, например):
   - Цена выросла до 102 USDT (прибыль 2%)
   - Устанавливаете БУ на уровне входа (100 USDT)
   - Активируете трейлинг стоп: trailing.activate(102.0)
   
2. ОТСЛЕЖИВАНИЕ:
   - Цена продолжает расти: 102 → 103 → 104 → 105
   - При каждом обновлении цены вызываете: trailing.update(текущая_цена)
   
3. АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ:
   - Цена 103.0: рост от 102 = 1% → стоп ставится на 102.9 (текущая цена - 0.1%)
   - Цена 104.05: рост от 103 = 1% → стоп ставится на 103.95 (текущая цена - 0.1%)
   - Цена 105.1: рост от 104.05 = 1% → стоп ставится на 105.0 (текущая цена - 0.1%)
   
   Важно: стоп ставится на ТЕКУЩУЮ цену с небольшим отступом (offset_percentage),
   чтобы защититься от проскальзывания при отправке запроса на биржу.
   
4. ЗАЩИТА ПРИБЫЛИ:
   - Если цена упадет до 103.5, стоп-лосс останется на 103.95
   - Позиция закроется автоматически, и вы останетесь в плюсе!
   
═══════════════════════════════════════════════════════════════════════════════
ПРИМЕР ВСТРОЙКИ В СУЩЕСТВУЮЩИЙ КОД:
═══════════════════════════════════════════════════════════════════════════════

from bybit_func.trailing_stop import TrailingStop
from bybit_func import session

# 1. Создаем объект трейлинг стопа (один раз в начале программы)
http_session = session.create_session(use_demo=True)
trailing = TrailingStop(
    symbol="BTCUSDT",
    session=http_session,
    trigger_percentage=1.0,  # Обновлять каждые 1%
    position_side="Buy",
    offset_percentage=0.1
)

# 2. Активируем при достижении БУ (в price_trigger_callback)
def price_trigger_callback():
    global current_price
    # ... ваш код установки БУ ...
    trailing.activate(current_price)  # Активируем трейлинг стоп

# 3. Обновляем при каждом получении цены (в handle_ticker_price)
def handle_ticker_price(message):
    global current_price
    current_price = float(message['data']['lastPrice'])
    
    # Если трейлинг стоп активен - обновляем его
    if trailing.is_active:
        trailing.update(current_price)

═══════════════════════════════════════════════════════════════════════════════
"""
from pybit.unified_trading import HTTP
from bybit_logic.bybit_func import orders
from logger_config import setup_logger

logger = setup_logger(__name__)


class TrailingStop:
    """
    Класс для управления трейлинг стоп-лоссом
    
    Трейлинг стоп автоматически двигает стоп-лосс вслед за ценой
    при достижении заданного процента изменения цены (например, каждые 1%).
    
    Как это работает:
    1. Вы активируете трейлинг стоп, указав стартовую цену (например, после установки БУ)
    2. При каждом обновлении цены вы вызываете метод update(current_price)
    3. Класс автоматически проверяет: выросла ли цена на заданный процент (trigger_percentage)
    4. Если да - устанавливает стоп-лосс на ТЕКУЩЕЙ цене с небольшим отступом (offset_percentage)
    5. Цикл повторяется: следующий стоп будет установлен через еще 1% роста
    
    Пример использования:
        # Создаем объект трейлинг стопа
        trailing = TrailingStop(
            symbol="BTCUSDT",
            session=http_session,
            trigger_percentage=1.0,  # Обновлять стоп каждые 1%
            position_side="Buy",     # Лонг позиция
            offset_percentage=0.1    # Отступ 0.1% от текущей цены (защита от проскальзывания)
        )
        
        # Активируем трейлинг стоп при цене 102 (после установки БУ)
        trailing.activate(102.0)
        
        # При каждом обновлении цены вызываем update()
        trailing.update(102.0)  # Цена 102 - не обновляется (рост 0%)
        trailing.update(103.0)  # Цена 103 - стоп ставится на 102.9 (рост 1% от 102)
        trailing.update(104.05) # Цена 104.05 - стоп ставится на 103.95 (рост 1% от 103)
        
        # Можно проверить состояние
        if trailing.is_active:
            print(f"Трейлинг стоп активен, последний стоп: {trailing.last_stop_price}")
    """
    
    def __init__(self, symbol: str, session: HTTP, trigger_percentage: float = 1.0,
                 position_side: str = "Buy", offset_percentage: float = 0.1):
        """
        Создает объект трейлинг стопа
        
        Args:
            symbol: Торговая пара (например: "BTCUSDT", "ETHUSDT")
            session: HTTP сессия Bybit (созданная через session.create_session())
            trigger_percentage: На сколько процентов должна вырасти цена для обновления стопа (по умолчанию 1.0%)
            position_side: Сторона позиции - "Buy" (лонг) или "Sell" (шорт)
            offset_percentage: Небольшой отступ от текущей цены для защиты от проскальзывания (по умолчанию 0.1%)
                              При установке стопа он будет на эту величину ниже/выше текущей цены
        
        Пример:
            trailing = TrailingStop("BTCUSDT", http_session, trigger_percentage=1.0)
        """
        self.symbol = symbol.upper()
        self.session = session
        self.trigger_percentage = trigger_percentage
        self.position_side = position_side
        self.offset_percentage = offset_percentage
        
        # Внутренние переменные состояния
        self.is_active = False  # Активирован ли трейлинг стоп
        self.last_update_price = None  # Цена, от которой отсчитываем процент роста
        self.last_stop_price = None  # Последняя установленная цена стоп-лосса
        self.highest_price = None  # Максимальная достигнутая цена
        
        logger.info(
            f"📊 Создан TrailingStop для {self.symbol} "
            f"(триггер: {trigger_percentage}%, сторона: {position_side})"
        )
    
    def activate(self, start_price: float):
        """
        Активирует трейлинг стоп с указанной стартовой цены
        
        После активации трейлинг стоп будет отслеживать изменения цены
        и автоматически обновлять стоп-лосс при достижении trigger_percentage.
        
        Args:
            start_price: Цена, с которой начинается отслеживание
        
        Пример:
            trailing.activate(100.0)  # Начинаем отслеживание с цены 100
        """
        if start_price is None or start_price <= 0:
            logger.error(f"❌ Некорректная стартовая цена: {start_price}")
            return False
        
        self.is_active = True
        self.last_update_price = start_price
        self.highest_price = start_price
        self.last_stop_price = None
        
        logger.info(f"🟢 Трейлинг стоп активирован для {self.symbol} на цене {start_price:.8g}")
        return True
    
    def deactivate(self):
        """
        Деактивирует трейлинг стоп
        
        После деактивации метод update() не будет обновлять стоп-лосс.
        """
        self.is_active = False
        logger.info(f"🔴 Трейлинг стоп деактивирован для {self.symbol}")
    
    def update(self, current_price: float) -> bool:
        """
        Обновляет трейлинг стоп на основе текущей цены
        
        Этот метод нужно вызывать каждый раз при получении новой цены
        (например, из WebSocket обновлений).
        
        Метод автоматически:
        - Проверяет, достигнут ли процент роста для обновления стопа
        - Устанавливает новый стоп-лосс, если условие выполнено
        - Обновляет внутренние переменные состояния
        
        Args:
            current_price: Текущая рыночная цена
        
        Returns:
            bool: True если стоп-лосс был обновлен, False в противном случае
        
        Пример:
            # В обработчике цены WebSocket:
            if trailing.update(current_price):
                print("Стоп-лосс обновлен!")
        """
        if not self.is_active:
            return False
        
        if current_price is None or current_price <= 0:
            logger.warning(f"⚠️ Некорректная текущая цена: {current_price}")
            return False
        
        if self.last_update_price is None:
            logger.warning("⚠️ Трейлинг стоп не был активирован! Вызовите activate() сначала.")
            return False
        
        # Обновляем максимальную цену
        if self.highest_price is None:
            self.highest_price = current_price
        else:
            if self.position_side == "Buy":
                # Для лонга: запоминаем максимальную цену
                if current_price > self.highest_price:
                    self.highest_price = current_price
            else:
                # Для шорта: запоминаем минимальную цену
                if current_price < self.highest_price:
                    self.highest_price = current_price
        
        # Проверяем условие обновления стоп-лосса
        price_change_percent = self._calculate_price_change(self.last_update_price, current_price)
        
        if price_change_percent >= self.trigger_percentage:
            # Условие выполнено - обновляем стоп-лосс
            return self._update_stop_loss(current_price)
        
        return False
    
    def _calculate_price_change(self, base_price: float, current_price: float) -> float:
        """
        Рассчитывает процент изменения цены от базовой
        
        Для лонга: (текущая - базовая) / базовая * 100
        Для шорта: (базовая - текущая) / базовая * 100
        """
        if self.position_side == "Buy":
            # Для лонга: прибыль = рост цены
            if base_price <= 0:
                return 0.0
            return ((current_price - base_price) / base_price) * 100
        else:
            # Для шорта: прибыль = падение цены
            if base_price <= 0:
                return 0.0
            return ((base_price - current_price) / base_price) * 100
    
    def _update_stop_loss(self, current_price: float) -> bool:
        """
        Внутренний метод для обновления стоп-лосса
        
        Устанавливает стоп-лосс на уровне ТЕКУЩЕЙ цены с небольшим отступом
        для защиты от проскальзывания при отправке запроса.
        
        Пример для лонга:
        - Цена выросла до 103 (рост на 1% от последней точки)
        - Устанавливаем стоп на 102.9 (103 - 0.1% отступ)
        """
        # Рассчитываем цену стоп-лосса на основе ТЕКУЩЕЙ цены
        if self.position_side == "Buy":
            # Для лонга: стоп-лосс чуть ниже текущей цены (защита от проскальзывания)
            target_stop_price = current_price * (100 - self.offset_percentage) / 100
            
            # Дополнительная проверка безопасности: стоп должен быть ниже текущей цены
            if target_stop_price >= current_price:
                # Это не должно происходить, но на всякий случай корректируем
                logger.warning(
                    f"⚠️ Рассчитанный стоп-лосс {target_stop_price:.8g} должен быть ниже "
                    f"текущей цены {current_price:.8g}. Корректирую..."
                )
                target_stop_price = current_price * 0.999  # Еще немного ниже
            
            # Обновляем только если новый стоп выше предыдущего (не двигаем стоп назад)
            if self.last_stop_price is not None and target_stop_price <= self.last_stop_price:
                logger.debug(
                    f"⏭ Пропускаю обновление: новый стоп {target_stop_price:.8g} не выше "
                    f"текущего {self.last_stop_price:.8g}"
                )
                return False
        
        else:  # position_side == "Sell"
            # Для шорта: стоп-лосс чуть выше текущей цены (защита от проскальзывания)
            target_stop_price = current_price * (100 + self.offset_percentage) / 100
            
            # Дополнительная проверка безопасности: стоп должен быть выше текущей цены
            if target_stop_price <= current_price:
                # Это не должно происходить, но на всякий случай корректируем
                logger.warning(
                    f"⚠️ Рассчитанный стоп-лосс {target_stop_price:.8g} должен быть выше "
                    f"текущей цены {current_price:.8g}. Корректирую..."
                )
                target_stop_price = current_price * 1.001  # Еще немного выше
            
            # Обновляем только если новый стоп ниже предыдущего (не двигаем стоп назад для шорта)
            if self.last_stop_price is not None and target_stop_price >= self.last_stop_price:
                logger.debug(
                    f"⏭ Пропускаю обновление: новый стоп {target_stop_price:.8g} не ниже "
                    f"текущего {self.last_stop_price:.8g}"
                )
                return False
        
        # Устанавливаем стоп-лосс через API
        logger.info(
            f"📝 Обновляю стоп-лосс для {self.symbol} до {target_stop_price:.8g} "
            f"(текущая цена: {current_price:.8g})"
        )
        
        result = orders.set_stop_loss(self.symbol, target_stop_price, self.session)
        
        if result and result.get('retCode') == 0:
            self.last_stop_price = target_stop_price
            self.last_update_price = current_price  # Обновляем базовую цену для следующего расчета
            
            logger.info(
                f"✅ Стоп-лосс обновлен: {target_stop_price:.8g} "
                f"(текущая цена: {current_price:.8g}, отступ: {self.offset_percentage:.2f}%)"
            )
            return True
        else:
            error_msg = result.get('retMsg', 'Неизвестная ошибка') if result else 'Нет ответа от сервера'
            logger.error(f"❌ Ошибка обновления стоп-лосса: {error_msg}")
            return False
    
    def get_status(self) -> dict:
        """
        Возвращает текущий статус трейлинг стопа
        
        Returns:
            dict: Словарь с информацией о состоянии трейлинг стопа
        
        Пример:
            status = trailing.get_status()
            print(f"Активен: {status['is_active']}")
            print(f"Последний стоп: {status['last_stop_price']}")
        """
        return {
            'is_active': self.is_active,
            'last_update_price': self.last_update_price,
            'last_stop_price': self.last_stop_price,
            'highest_price': self.highest_price,
            'trigger_percentage': self.trigger_percentage,
            'position_side': self.position_side
        }

    def set_initial_stop(self, current_price: float) -> bool:
        """
        Устанавливает начальный стоп-лосс сразу после активации,
        если прибыль уже превышает целевой процент
        
        Args:
            current_price: Текущая рыночная цена
        
        Returns:
            bool: True если стоп-лосс был установлен, False в противном случае
        """
        if not self.is_active:
            logger.warning("⚠️ Трейлинг стоп не активирован! Сначала вызовите activate()")
            return False
        
        if self.last_stop_price is not None:
            logger.debug("ℹ️ Стоп-лосс уже установлен, используйте update() для обновления")
            return False
        
        # Устанавливаем начальный стоп через _update_stop_loss
        return self._update_stop_loss(current_price)


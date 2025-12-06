"""
Модуль для подключения к WebSocket стриму цены Bybit

Простое и понятное подключение к публичному WebSocket для мониторинга цены монеты
"""
from pybit.unified_trading import WebSocket
from logger_config import setup_logger
import time

logger = setup_logger(__name__)


class PriceStream:
    """
    Класс для подключения к WebSocket стриму цены
    
    Использование:
        # Создаем обработчик цены
        def my_price_handler(message):
            price = message['data']['lastPrice']
            print(f"Текущая цена: {price}")
        
        # Подключаемся к стриму
        stream = PriceStream("BTCUSDT", my_price_handler)
        stream.start()  # Запускаем мониторинг
        
        # ... ваш код ...
        
        stream.stop()  # Останавливаем мониторинг
    """
    
    def __init__(self, symbol, price_handler, testnet=False):
        """
        Создает подключение к WebSocket стриму
        
        Args:
            symbol (str): Торговая пара (например: "BTCUSDT", "ETHUSDT")
            price_handler (function): Функция, которая будет вызываться при каждом обновлении цены
                                     Должна принимать один параметр: message (dict)
            testnet (bool): True = тестовый сервер, False = основной сервер
        """
        self.symbol = symbol
        self.price_handler = price_handler
        self.testnet = testnet
        self.ws = None
        self.is_running = False
        
        logger.info(f"📡 Создан PriceStream для {symbol}")
    
    def _handle_message(self, message):
        """
        Внутренний обработчик сообщений от WebSocket
        Вызывает пользовательскую функцию price_handler
        """
        try:
            # Вызываем пользовательскую функцию обработки
            self.price_handler(message)
        except Exception as e:
            logger.error(f"❌ Ошибка в обработчике цены: {e}")
    
    def start(self):
        """
        Запускает подключение к WebSocket и начинает мониторинг цены
        
        После вызова этой функции:
        - price_handler будет вызываться автоматически при каждом обновлении цены
        - Программа будет работать до вызова stop() или нажатия Ctrl+C
        """
        if self.is_running:
            logger.warning("⚠️ WebSocket уже запущен")
            return
        
        try:
            logger.info(f"🔌 Подключаюсь к WebSocket для {self.symbol}...")
            
            # Создаем WebSocket соединение (публичный канал, не требует API ключи)
            self.ws = WebSocket(
                channel_type="linear",  # Тип канала: linear = USDT фьючерсы
                testnet=self.testnet
            )
            
            # Подписываемся на обновления цены для нашего символа
            self.ws.ticker_stream(self.symbol, self._handle_message)
            
            self.is_running = True
            logger.info(f"✅ Подписка на обновления цены {self.symbol} активна")
            logger.info("💡 Используйте stop() для остановки или нажмите Ctrl+C")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при подключении к WebSocket: {e}")
            self.is_running = False
            raise
    
    def stop(self):
        """
        Останавливает WebSocket соединение
        """
        if not self.is_running:
            logger.warning("⚠️ WebSocket не запущен")
            return
        
        try:
            if self.ws:
                self.ws.exit()
                logger.info("⏹ WebSocket соединение закрыто")
            self.is_running = False
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке WebSocket: {e}")
    
    def run_forever(self):
        """
        Запускает WebSocket и держит программу работающей до нажатия Ctrl+C
        
        Это удобный метод, который объединяет start() и бесконечный цикл
        """
        self.start()
        
        try:
            # Держим программу запущенной, чтобы WebSocket продолжал работать
            # Функция price_handler будет вызываться автоматически при каждом обновлении цены
            while self.is_running:
                time.sleep(1)  # Спим 1 секунду, чтобы не нагружать процессор
        except KeyboardInterrupt:
            # Пользователь нажал Ctrl+C - останавливаем программу
            logger.info("\n⏹ Остановка по запросу пользователя...")
            self.stop()
        except Exception as e:
            logger.error(f"❌ Ошибка в WebSocket соединении: {e}")
            self.stop()
            raise


def start_price_monitoring(symbol, price_handler, testnet=False):
    """
    Простая функция для быстрого запуска мониторинга цены
    
    Args:
        symbol (str): Торговая пара (например: "BTCUSDT")
        price_handler (function): Функция для обработки обновлений цены
        testnet (bool): True = тестовый сервер, False = основной
    
    Пример использования:
        def handle_price(message):
            price = message['data']['lastPrice']
            print(f"Цена: {price}")
        
        start_price_monitoring("BTCUSDT", handle_price)
    """
    stream = PriceStream(symbol, price_handler, testnet)
    stream.run_forever()


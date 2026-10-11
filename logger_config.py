import logging
import os
from datetime import datetime


class DailyFileHandler(logging.FileHandler):
    """
    Пишет в logs/YYYY-MM-DD.log по ТЕКУЩЕЙ дате и переключает файл в полночь.

    Раньше файл фиксировался в момент старта процесса, и долгоживущие процессы неделями
    писали в «старый» файл. Файлы не переименовываются (в отличие от TimedRotatingFileHandler),
    поэтому несколько процессов могут безопасно дописывать в один и тот же файл.
    """

    def __init__(self, log_dir: str, encoding: str = "utf-8") -> None:
        self._log_dir = log_dir
        self._current_date = self._today()
        super().__init__(self._path_for(self._current_date), encoding=encoding, delay=True)

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _path_for(self, date_str: str) -> str:
        return os.path.abspath(os.path.join(self._log_dir, f"{date_str}.log"))

    def emit(self, record: logging.LogRecord) -> None:
        today = self._today()
        if today != self._current_date:
            self.acquire()
            try:
                if today != self._current_date:
                    self.close()
                    self._current_date = today
                    self.baseFilename = self._path_for(today)
            finally:
                self.release()
        super().emit(record)


def setup_logger(name: str) -> logging.Logger:
    """
    Настройка логгера с записью в файл и консоль
    
    Args:
        name: Имя логгера
        
    Returns:
        logging.Logger: Настроенный логгер
    """
    # Создаем директорию для логов, если её нет
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Создаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        # Повторный вызов для того же имени не должен дублировать строки в логе.
        return logger

    # Создаем форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Настраиваем файловый обработчик (файл по текущей дате, переключается в полночь)
    file_handler = DailyFileHandler(log_dir)
    file_handler.setFormatter(formatter)
    
    # Настраиваем консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Добавляем обработчики
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

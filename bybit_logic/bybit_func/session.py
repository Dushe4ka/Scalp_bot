"""
Модуль для создания HTTP сессии Bybit
"""
from pybit.unified_trading import HTTP
from bybit_logic.config import API_KEY, API_SECRET, DEMO_API_KEY, DEMO_API_SECRET
from logger_config import setup_logger

logger = setup_logger(__name__)


def create_session(
    use_demo: bool = True,
    testnet: bool = False,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> HTTP:
    """
    Создает HTTP сессию для работы с Bybit API
    
    Args:
        use_demo: Использовать демо-счет (по умолчанию True)
        testnet: Использовать testnet (по умолчанию False)
        api_key: Пользовательский API key (опционально)
        api_secret: Пользовательский API secret (опционально)
    
    Returns:
        HTTP: Объект сессии Bybit
    """
    final_api_key = api_key if api_key is not None else (DEMO_API_KEY if use_demo else API_KEY)
    final_api_secret = api_secret if api_secret is not None else (DEMO_API_SECRET if use_demo else API_SECRET)
    
    if not final_api_key or not final_api_secret:
        raise ValueError(
            f"API ключи не найдены. use_demo={use_demo}. "
            f"Проверьте настройки в config.py"
        )
    
    session = HTTP(
        testnet=testnet,
        api_key=final_api_key,
        api_secret=final_api_secret,
        demo=use_demo
    )
    
    logger.debug(f"Создана HTTP сессия Bybit (demo={use_demo}, testnet={testnet})")
    
    return session



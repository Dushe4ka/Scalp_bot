import re
from fastapi import HTTPException
from database.users_repository import db
from bybit_logic.bybit_func import session
from config import USE_DEMO

def validate_and_clean_symbol(symbol: str) -> str:
    """
    Валидирует и очищает символ торговой пары
    
    Убирает лишние символы после точки (например, .P, .PERP и т.д.)
    и возвращает чистый символ в верхнем регистре
    
    Args:
        symbol: Символ торговой пары (например, "ZEUSUSDT.P" или "BTCUSDT")
    
    Returns:
        str: Очищенный символ в верхнем регистре (например, "ZEUSUSDT")
    
    Raises:
        ValueError: Если символ невалиден или пустой
    
    Examples:
        >>> validate_and_clean_symbol("ZEUSUSDT.P")
        'ZEUSUSDT'
        >>> validate_and_clean_symbol("btcusdt")
        'BTCUSDT'
        >>> validate_and_clean_symbol("ETHUSDT.PERP")
        'ETHUSDT'
    """
    if not symbol:
        raise ValueError("Символ не может быть пустым")
    
    # Приводим к верхнему регистру и убираем пробелы
    symbol = symbol.strip().upper()
    
    # Убираем все после точки (например, .P, .PERP, .PERPETUAL и т.д.)
    if '.' in symbol:
        symbol = symbol.split('.')[0]
    
    # Убираем лишние пробелы (на случай если они остались)
    symbol = symbol.strip()
    
    # Базовая валидация формата
    # и содержать только буквы и цифры
    
    if not re.match(r'^[A-Z0-9]+$', symbol):
        raise ValueError(f"Символ содержит недопустимые символы: {symbol}. Разрешены только буквы и цифры")
    
    # Проверяем, что символ заканчивается на известные суффиксы (опционально)
    # Это необязательная проверка, но может помочь отфильтровать некорректные символы
    common_suffixes = ['USDT', 'USDC', 'BTC', 'ETH', 'USD']
    has_valid_suffix = any(symbol.endswith(suffix) for suffix in common_suffixes)
    
    if not has_valid_suffix:
        # Не выбрасываем ошибку, просто предупреждаем в логе
        # Могут быть другие валидные суффиксы
        pass
    
    return symbol


def parse_short_signal_body(raw_body: str) -> tuple[str, bool]:
    """
    Разбирает тело вебхука /short_3_limit: тикер + опциональный маркер типа алерта.

    Поддерживаемые форматы (маркер — всё после первого пробела, регистронезависимо):
    - "{ticker}"               -> обычный режим (маркер отсутствует)
    - "{ticker} SHORT SIGNAL"  -> обычный режим (текущая логика)
    - "{ticker} Short1"        -> режим повышенного риска (тейк 1%, стоп 10%, без усреднений)

    Любой другой/неизвестный маркер трактуется как обычный режим — безопасный дефолт.

    Args:
        raw_body: Сырое тело POST-запроса от TradingView

    Returns:
        tuple[str, bool]: (очищенный символ, risk_mode)

    Raises:
        ValueError: Если тело пустое или тикер невалиден
    """
    raw = (raw_body or "").strip()
    if not raw:
        raise ValueError("Символ не может быть пустым")

    ticker_part, _, marker_part = raw.partition(" ")
    symbol = validate_and_clean_symbol(ticker_part)
    marker = marker_part.strip().upper()
    risk_mode = marker == "SHORT1"
    return symbol, risk_mode


async def get_user_http_session_or_404(tg_id: int):
    """
    Возвращает Bybit HTTP-сессию пользователя по tg_id.
    Поднимает HTTPException(404/400), если пользователь/ключи невалидны.
    """
    user = await db.get_user(int(tg_id))
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    bybit_data = user.get("bybit_data") or {}
    api_key = (bybit_data.get("api_key") or "").strip()
    api_secret = (bybit_data.get("api_secret") or "").strip()
    if not api_key or not api_secret:
        raise HTTPException(status_code=400, detail="У пользователя не указаны API key/secret")

    return session.create_session(use_demo=USE_DEMO, api_key=api_key, api_secret=api_secret)
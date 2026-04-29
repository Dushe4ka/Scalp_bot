import re

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
from pybit.unified_trading import HTTP
from logger_config import setup_logger
from typing import Optional, Dict, Any
from datetime import datetime

logger = setup_logger(__name__)


def get_positions_by_symbol(session: HTTP, symbol: str) -> dict:
    """
    Получает позиции по символу
    """
    try:    
        return session.get_positions(
                category="linear",
                symbol=symbol
                )
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return None

def get_last_position_by_symbol(session: HTTP, symbol: str) -> dict:
    """
    Получает последнюю позицию по символу
    """
    positions = get_positions_by_symbol(session, symbol)
    if positions and positions.get('result', {}).get('list'):
        return positions['result']['list'][0]
    else:
        return None

def get_all_positions(session: HTTP) -> dict:
    """
    Получает все позиции
    """
    try:
        return session.get_positions(
        category="linear"
    )
    except Exception as e:
        logger.error(f"Error getting all positions: {e}")
        return None

def if_position_open(session: HTTP, symbol: str) -> bool:
    """
    Проверяет, открыта ли позиция по символу
    """
    positions = get_positions_by_symbol(session, symbol)
    
    if positions and positions.get('result', {}).get('list'):
        position_info = positions['result']['list'][0]
        
        # ✅ ПРОВЕРКА: Позиция открыта только если размер больше 0
        position_size = float(position_info.get('size', 0))
        if position_size > 0:
            return True
        else:
            return False

def get_last_position_info(session: HTTP, symbol: str) -> Optional[Dict[str, Any]]:
    """
    Получает информацию о последней позиции (открытой или закрытой) для указанного символа
    
    Args:
        session: HTTP сессия Bybit
        symbol: Торговая пара (например: "BTCUSDT")
    
    Returns:
        dict: Словарь с информацией о позиции или None, если позиция не найдена
        
        Структура возвращаемых данных:
        {
            'symbol': str,              # Символ (например: "BTCUSDT")
            'side': str,                # Сторона позиции ("Buy" или "Sell")
            'size': float,              # Размер позиции
            'entry_price': float,       # Цена входа
            'exit_price': Optional[float],  # Цена выхода (None если позиция открыта)
            'pnl_usdt': float,          # Прибыль/убыток в USDT
            'open_time': Optional[datetime],  # Время открытия позиции
            'close_time': Optional[datetime], # Время закрытия позиции (None если открыта)
            'is_open': bool             # True если позиция открыта, False если закрыта
        }
    """
    try:
        symbol = symbol.upper()
        
        # 1. Сначала проверяем текущую позицию (может быть открыта)
        position_data = get_positions_by_symbol(session, symbol)
        
        if position_data and position_data.get('result', {}).get('list'):
            position_info = position_data['result']['list'][0]
            position_size = float(position_info.get('size', 0))
            
            # Если позиция открыта
            if position_size > 0:
                created_time = int(position_info.get('createdTime', 0)) / 1000
                open_time = datetime.fromtimestamp(created_time) if created_time else None
                
                return {
                    'symbol': symbol,
                    'side': position_info.get('side', ''),
                    'size': position_size,
                    'entry_price': float(position_info.get('avgPrice', 0)),
                    'exit_price': None,
                    'pnl_usdt': float(position_info.get('unrealisedPnl', 0)) if position_info.get('unrealisedPnl') else 0.0,
                    'open_time': open_time,
                    'close_time': None,
                    'is_open': True
                }
        
        # 2. Если позиция закрыта, получаем информацию из истории закрытых PnL
        closed_pnl = session.get_closed_pnl(
            category="linear",
            symbol=symbol,
            limit=1  # Только последняя закрытая позиция
        )
        
        if closed_pnl and closed_pnl.get('result', {}).get('list'):
            pnl_list = closed_pnl['result']['list']
            
            if pnl_list:
                pnl_item = pnl_list[0]  # Последняя закрытая позиция
                
                created_time = int(pnl_item.get('createdTime', 0)) / 1000
                updated_time = int(pnl_item.get('updatedTime', 0)) / 1000
                
                open_time = datetime.fromtimestamp(created_time) if created_time else None
                close_time = datetime.fromtimestamp(updated_time) if updated_time else None
                
                return {
                    'symbol': pnl_item.get('symbol', symbol),
                    'side': pnl_item.get('side', ''),
                    'size': float(pnl_item.get('qty', 0)),
                    'entry_price': float(pnl_item.get('avgEntryPrice', 0)),
                    'exit_price': float(pnl_item.get('avgExitPrice', 0)),
                    'pnl_usdt': float(pnl_item.get('closedPnl', 0)),
                    'open_time': open_time,
                    'close_time': close_time,
                    'is_open': False
                }
        
        # Если ничего не найдено
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о последней позиции для {symbol}: {e}")
        return None

def result_position_info(symbol: str, session: HTTP) -> Optional[str]:
    """
    Формирует и возвращает итоговую информацию о позиции в виде текста
    
    Args:
        symbol: Торговая пара (например: "BTCUSDT")
        session: HTTP сессия Bybit
    
    Returns:
        str: Компактный текст с информацией о позиции или None, если позиция не найдена
    """
    position_info = get_last_position_info(session, symbol)

    if position_info:
        lines = []
        lines.append(f"📊 Позиция: {position_info['symbol']}")
        
        # Статус
        status = "🟢 Открыта" if position_info['is_open'] else "🔴 Закрыта"
        lines.append(f"Статус: {status}")
        
        # Сторона
        side_text = "Лонг" if position_info['side'] == 'Buy' else "Шорт"
        lines.append(f"Сторона: {side_text}")
        
        # Размер и цены
        lines.append(f"Размер: {position_info['size']}")
        lines.append(f"Цена входа: {position_info['entry_price']:.8g}")
        
        if position_info['exit_price']:
            lines.append(f"Цена выхода: {position_info['exit_price']:.8g}")
        
        # Время
        if position_info['open_time']:
            lines.append(f"Открыта: {position_info['open_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        if position_info['close_time']:
            lines.append(f"Закрыта: {position_info['close_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        # PnL
        pnl = position_info['pnl_usdt']
        if pnl > 0:
            lines.append(f"💰 PnL: +{pnl:.2f} USDT")
        elif pnl < 0:
            lines.append(f"❌ PnL: {pnl:.2f} USDT")
        else:
            lines.append(f"⚪ PnL: {pnl:.2f} USDT")
        
        # Изменение цены (только для закрытых позиций)
        if not position_info['is_open'] and position_info['entry_price'] > 0:
            entry = position_info['entry_price']
            exit_price = position_info['exit_price']
            
            if exit_price and exit_price > 0:
                if position_info['side'] == 'Buy':
                    percent_change = ((exit_price - entry) / entry) * 100
                else:  # Sell
                    percent_change = ((entry - exit_price) / entry) * 100
                
                lines.append(f"📈 Изменение: {percent_change:+.2f}%")
        
        return "\n".join(lines)
        
    else:
        return "❌ Позиция не найдена"


def result_position_info_data(symbol: str, session: HTTP) -> Optional[Dict[str, Any]]:
    """
    Возвращает структурированные данные по последней позиции.
    """
    return get_last_position_info(session, symbol)